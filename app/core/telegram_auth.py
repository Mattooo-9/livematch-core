"""
Validates Telegram WebApp initData (HMAC-SHA256 per Telegram's documented scheme)
so the mini-app's API calls can't be spoofed by an arbitrary HTTP client.
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from app.core.config import settings


def validate_init_data(init_data: str, max_age_seconds: int = 86400) -> dict | None:
    if not init_data or not settings.BOT_TOKEN:
        return None

    parsed = dict(parse_qsl(init_data, strict_parsing=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = int(parsed.get("auth_date", "0"))
    import time

    if time.time() - auth_date > max_age_seconds:
        return None

    user_raw = parsed.get("user")
    user = json.loads(user_raw) if user_raw else None
    return {"user": user, "auth_date": auth_date, "raw": parsed}
