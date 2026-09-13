# -*- coding: utf-8 -*-
import hashlib
import hmac
import time

from fastapi import Request

from app.config import get_settings

ADMIN_COOKIE = "admin_access"
_PAYLOAD_PREFIX = "admin"


def _sign(payload: str) -> str:
    settings = get_settings()
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        f"{_PAYLOAD_PREFIX}.{payload}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def make_admin_cookie() -> tuple:
    settings = get_settings()
    max_age = settings.admin_session_hours * 3600
    expires = int(time.time()) + max_age
    payload = str(expires)
    return f"{payload}.{_sign(payload)}", max_age


def is_admin_unlocked(request: Request) -> bool:
    cookie = request.cookies.get(ADMIN_COOKIE)
    if not cookie or "." not in cookie:
        return False
    payload, sig = cookie.split(".", 1)
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    try:
        expires = int(payload)
    except ValueError:
        return False
    return expires > int(time.time())


def check_admin_password(password: str) -> bool:
    expected = get_settings().admin_password
    if not expected:
        return False
    return hmac.compare_digest(password, expected)