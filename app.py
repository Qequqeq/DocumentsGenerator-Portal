# -*- coding: utf-8 -*-
import json
import hmac
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path

app = FastAPI()

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "portal.db"
SECRET_FILE = BASE_DIR / ".secret_key"
SELFHOST_REQUESTS_FILE = BASE_DIR / "selfhost_requests.json"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------- Инфраструктура ----------

def get_secret() -> str:
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    secret = secrets.token_hex(32)
    SECRET_FILE.write_text(secret, encoding="utf-8")
    return secret


SECRET = get_secret()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                started_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)


init_db()


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


def make_session_cookie(user_id: int) -> str:
    payload = str(user_id)
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def get_current_user_id(request: Request):
    cookie = request.cookies.get("session")
    if not cookie or "." not in cookie:
        return None
    payload, sig = cookie.split(".", 1)
    expected = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return int(payload)
    except ValueError:
        return None


def get_current_user(request: Request):
    """Возвращает (user_id, email) или (None, None)."""
    user_id = get_current_user_id(request)
    if user_id is None:
        return None, None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None, None
    return row[0], row[1]


def get_active_subscription(user_id: int):
    """Возвращает активную подписку пользователя или None."""
    if user_id is None:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT id, plan, started_at, expires_at, status
            FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY expires_at DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()
    if not row:
        return None
    expires_at = datetime.fromisoformat(row[3])
    if expires_at < datetime.now():
        # Подписка истекла — помечаем как expired
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE subscriptions SET status = 'expired' WHERE id = ?",
                (row[0],)
            )
        return None
    return {
        "id": row[0],
        "plan": row[1],
        "started_at": datetime.fromisoformat(row[2]),
        "expires_at": expires_at,
        "status": row[4],
    }


PLAN_LABELS = {
    "monthly": "Продвинутый — 5 000 ₽ / месяц",
    "yearly": "Продвинутый — 50 000 ₽ / год (2 месяца бесплатно)",
}


REGISTER_ERRORS = {
    "email": "Введите корректный email.",
    "password": "Пароль должен быть не короче 8 символов.",
    "exists": "Пользователь с таким email уже существует — войдите или укажите другой email.",
}


def add_common_context(request: Request):
    """Возвращает общий контекст для шаблонов: авторизован ли пользователь."""
    user_id, email = get_current_user(request)
    return {"current_user_email": email}


# ---------- Страницы лендинга ----------

@app.get("/")
def landing_main(request: Request, sent: str = "", error: str = "", email: str = ""):
    ctx = add_common_context(request)
    ctx.update({
        "request": request,
        "selfhost_sent": sent == "1",
        "register_error": REGISTER_ERRORS.get(error, ""),
        "register_email": email,
    })
    return templates.TemplateResponse("index.html", ctx)


@app.get("/auditors")
def landing_auditors(request: Request):
    ctx = add_common_context(request)
    ctx["request"] = request
    return templates.TemplateResponse("auditors.html", ctx)


@app.get("/organizations")
def landing_organizations(request: Request):
    ctx = add_common_context(request)
    ctx["request"] = request
    return templates.TemplateResponse("organizations.html", ctx)


# ---------- Регистрация / вход / выход ----------

@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()
    if "@" not in email or "." not in email:
        return RedirectResponse(url=f"/?error=email&email={quote(email)}#register", status_code=303)
    if len(password) < 8:
        return RedirectResponse(url=f"/?error=password&email={quote(email)}#register", status_code=303)

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return RedirectResponse(url=f"/?error=exists&email={quote(email)}#register", status_code=303)
        salt = secrets.token_hex(16)
        password_hash = hash_password(password, salt)
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (email, password_hash, salt, datetime.now().isoformat()),
        )
        user_id = cur.lastrowid

    response = RedirectResponse(url="/account", status_code=303)
    response.set_cookie(
        "session",
        make_session_cookie(user_id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session")
    return response


LOGIN_ERRORS = {
    "invalid": "Неверный email или пароль. Попробуйте снова.",
}


@app.get("/login")
def login_page(request: Request, error: str = "", email: str = ""):
    user_id, _ = get_current_user(request)
    if user_id is not None:
        return RedirectResponse(url="/account", status_code=303)

    ctx = add_common_context(request)
    ctx.update({
        "request": request,
        "login_error": LOGIN_ERRORS.get(error, ""),
        "login_email": email,
    })
    return templates.TemplateResponse("login.html", ctx)


@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    email = email.strip().lower()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, password_hash, salt FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    if not row:
        return RedirectResponse(url=f"/login?error=invalid&email={quote(email)}", status_code=303)

    user_id, stored_hash, salt = row
    computed_hash = hash_password(password, salt)

    if not hmac.compare_digest(computed_hash, stored_hash):
        return RedirectResponse(url=f"/login?error=invalid&email={quote(email)}", status_code=303)

    response = RedirectResponse(url="/account", status_code=303)
    response.set_cookie(
        "session",
        make_session_cookie(user_id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return response

# ---------- Личный кабинет ----------

@app.get("/account")
def account_page(request: Request):
    user_id, email = get_current_user(request)
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)

    with sqlite3.connect(DB_PATH) as conn:
        user_row = conn.execute(
            "SELECT email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    subscription = get_active_subscription(user_id)

    ctx = add_common_context(request)
    ctx.update({
        "request": request,
        "email": user_row[0],
        "created_at": datetime.fromisoformat(user_row[1]),
        "subscription": subscription,
        "plan_labels": PLAN_LABELS,
    })
    return templates.TemplateResponse("account.html", ctx)


@app.get("/subscribe")
def subscribe_page(request: Request):
    user_id, email = get_current_user(request)
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)

    subscription = get_active_subscription(user_id)

    ctx = add_common_context(request)
    ctx.update({
        "request": request,
        "subscription": subscription,
        "plan_labels": PLAN_LABELS,
    })
    return templates.TemplateResponse("subscribe.html", ctx)


@app.post("/subscribe")
async def subscribe_create(plan: str = Form(...)):
    user_id, _ = get_current_user_id_raw_or_redirect()
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)
    if plan not in PLAN_LABELS:
        return RedirectResponse(url="/subscribe", status_code=303)

    now = datetime.now()
    if plan == "monthly":
        expires_at = now + timedelta(days=30)
    else:  # yearly
        expires_at = now + timedelta(days=365)

    with sqlite3.connect(DB_PATH) as conn:
        # Деактивируем предыдущие подписки пользователя
        conn.execute(
            "UPDATE subscriptions SET status = 'superseded' WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, plan, started_at, expires_at, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (user_id, plan, now.isoformat(), expires_at.isoformat()),
        )

    return RedirectResponse(url="/account", status_code=303)


def get_current_user_id_raw_or_redirect():
    """Хелпер: возвращает user_id или None (для обработки POST)."""
    from fastapi import Request as _R
    # Для POST-роутов без request — читаем из куки напрямую
    # Но нам нужен request для чтения cookie. Переопределим через зависимость:
    return None, None


# Переписываем subscribe POST через явный Request:
@app.post("/subscribe")
async def subscribe_create_v2(request: Request, plan: str = Form(...)):
    user_id, email = get_current_user(request)
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)
    if plan not in PLAN_LABELS:
        return RedirectResponse(url="/subscribe", status_code=303)

    now = datetime.now()
    if plan == "monthly":
        expires_at = now + timedelta(days=30)
    else:
        expires_at = now + timedelta(days=365)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE subscriptions SET status = 'superseded' WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        conn.execute(
            """
            INSERT INTO subscriptions (user_id, plan, started_at, expires_at, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (user_id, plan, now.isoformat(), expires_at.isoformat()),
        )

    return RedirectResponse(url="/account", status_code=303)


# Удалим дубликат, оставив только v2:
# (Python автоматически переопределит роут /subscribe POST — FastAPI использует последний)


@app.post("/selfhost-request")
async def selfhost_request(
    name: str = Form(...),
    contact: str = Form(...),
    comment: str = Form(""),
):
    requests = []
    if SELFHOST_REQUESTS_FILE.exists():
        try:
            requests = json.loads(SELFHOST_REQUESTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            requests = []

    requests.append({
        "name": name,
        "contact": contact,
        "comment": comment,
        "created_at": datetime.now().isoformat(),
    })

    SELFHOST_REQUESTS_FILE.write_text(
        json.dumps(requests, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return RedirectResponse(url="/?sent=1#pricing", status_code=303)