# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.landing.service import SelfHostService

router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


@router.get("/")
async def landing_main(
    request: Request,
    current_user: User | None = Depends(get_current_user),
    sent: str = "",
    error: str = "",
    email: str = "",
):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "selfhost_sent": sent == "1",
            "register_error": error,
            "register_email": email,
            "current_user_email": current_user.email if current_user else None,
        },
    )


@router.post("/selfhost-request")
async def selfhost_request(
    name: str = Form(...),
    contact: str = Form(...),
    comment: str = Form(""),
):
    SelfHostService.add_request(name, contact, comment)
    return RedirectResponse(url="/?sent=1#pricing", status_code=303)