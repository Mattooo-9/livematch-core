"""Standalone background-worker entrypoint (chat sweep + daily AI insight).
Run as a separate process in production: `make worker` / docker-compose `worker` service."""
import asyncio
import signal

from app.tasks.scheduler import start_scheduler, stop_scheduler


async def main():
    await start_scheduler()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass  # Windows fallback
    await stop.wait()
    await stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
