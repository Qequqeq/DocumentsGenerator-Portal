# -*- coding: utf-8 -*-
import hashlib
import hmac

import bcrypt

from app.config import get_settings


class PasswordService:
    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class SessionService:
    @staticmethod
    def create_session_cookie(user_id: int) -> str:
        settings = get_settings()
        payload = str(user_id)
        sig = hmac.new(
            settings.secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{payload}.{sig}"

    @staticmethod
    def parse_session_cookie(cookie: str | None) -> int | None:
        if not cookie or "." not in cookie:
            return None

        settings = get_settings()
        payload, sig = cookie.split(".", 1)
        expected = hmac.new(
            settings.secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(sig, expected):
            return None

        try:
            return int(payload)
        except ValueError:
            return None