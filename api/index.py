"""
Vercel serverless function — PASSIVE (secondary) node.
Handles Telegram webhook ONLY when Koyeb (primary) is down.
Distributed lock ensures only one node processes updates.
"""
from __future__ import annotations
import asyncio, json, os
from http.server import BaseHTTPRequestHandler


def _async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence default logging

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "role": "secondary", "node": "vercel"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/webhook/telegram/"):
            secret = self.path.split("/")[-1]
            from app.core.config import settings
            if secret != settings.BOT_WEBHOOK_SECRET:
                self._respond(403, {"error": "forbidden"})
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                result = _async(self._process_update(body))
                self._respond(200, result)
            except Exception as e:
                self._respond(500, {"error": str(e)})
        else:
            self._respond(404, {"error": "not found"})

    async def _process_update(self, body: bytes) -> dict:
        from app.core.distributed_lock import try_acquire_lock, is_leader
        from aiogram.types import Update
        from app.bot.bot import get_bot, get_dispatcher

        # Try to acquire lock — if Koyeb is alive, it holds the lock
        # and this node is a no-op (returns ok without processing)
        if not await try_acquire_lock():
            # Primary is alive — silently ack without processing
            return {"ok": True, "processed": False, "reason": "primary_active"}

        # Primary is down — we're now active
        data = json.loads(body)
        update = Update.model_validate(data)
        bot = get_bot()
        dp  = get_dispatcher()
        await dp.feed_update(bot, update)
        return {"ok": True, "processed": True, "reason": "failover_active"}

    def _respond(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
