# -*- coding: utf-8 -*-
import json
from typing import Any
from urllib.parse import quote
from fastapi.responses import RedirectResponse


def make_flash_payload(text: str, level: str = "info") -> str:
    # JSON payload is percent-encoded to be safe for Set-Cookie header
    return quote(json.dumps({"text": text, "level": level}))


def redirect_with_flash(url: str, text: str, level: str = "info", max_age: int = 10) -> RedirectResponse:
    """Return a RedirectResponse that also sets a short-lived `flash` cookie.

    The cookie value is JSON: {text, level}. JS on the client reads it and shows a toast,
    then clears the cookie.
    """
    resp = RedirectResponse(url, status_code=303)
    payload = make_flash_payload(text or "", level or "info")
    # Not httponly so client JS can read it; short max_age
    resp.set_cookie("flash", payload, max_age=max_age, path="/")
    return resp
