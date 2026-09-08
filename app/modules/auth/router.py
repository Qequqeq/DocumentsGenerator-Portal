# -*- coding: utf-8 -*-
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.modules.auth.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.service import PasswordService, SessionService

router = APIRouter()

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


REGISTER_ERRORS = {
    "email": "Введите корректный email.",
    "password": "Пароль должен быть не короче 8 символов.",
    "exists": "Пользователь с таким email уже существует. Войдите в свой аккаунт или укажите другой email.",
}

LOGIN_ERRORS = {
    "invalid": "Неверный email или пароль. Попробуйте снова.",
}


@router.post("/register")
async def register(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    email = email.strip().lower()
    if "@" not in email or "." not in email:
        return RedirectResponse(
            url=f"/?error=email&email={quote(email)}#register",
            status_code=303,
        )

    if len(password) < 8:
        return RedirectResponse(
            url=f"/?error=password&email={quote(email)}#register",
            status_code=303,
        )

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        return RedirectResponse(
            url=f"/?error=exists&email={quote(email)}#register",
            status_code=303,
        )

    user = User(
        email=email,
        password_hash=PasswordService.hash_password(password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    response = RedirectResponse(url="/account", status_code=303)
    response.set_cookie(
        "session",
        SessionService.create_session_cookie(user.id),
        httponly=True,
        samesite="lax",
        max_age=settings.session_max_age_days * 24 * 60 * 60,
    )
    return response


@router.get("/login")
async def login_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
    error: str = "",
    email: str = "",
):
    if current_user is not None:
        return RedirectResponse(url="/account", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "login_error": LOGIN_ERRORS.get(error, ""),
            "login_email": email,
            "current_user_email": None,
        },
    )


@router.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    email = email.strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not PasswordService.verify_password(password, user.password_hash):
        return RedirectResponse(
            url=f"/login?error=invalid&email={quote(email)}",
            status_code=303,
        )

    response = RedirectResponse(url="/account", status_code=303)
    response.set_cookie(
        "session",
        SessionService.create_session_cookie(user.id),
        httponly=True,
        samesite="lax",
        max_age=settings.session_max_age_days * 24 * 60 * 60,
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session")
    return response