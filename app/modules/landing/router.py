# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.models import Subscription
from app.modules.subscriptions.service import SubscriptionService
from app.shared.templating import templates
from app.shared.flash import redirect_with_flash

from app.config import get_settings
from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.landing.service import SelfHostService

router = APIRouter()


@router.get("/")
async def landing_main(
    request: Request,
    current_user: User | None = Depends(get_current_user),
    sent: str = "",
    error: str = "",
    email: str = "",
    db: AsyncSession = Depends(get_db),
):
    sub = None
    if current_user:
        sub = await SubscriptionService.get_active_subscription(db, current_user.id)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "register_error": error,
            "register_email": email,
            "current_user_email": current_user.email if current_user else None,
            "sub": sub
        },
    )


@router.post("/selfhost-request")
async def selfhost_request(
    name: str = Form(...),
    contact: str = Form(...),
    comment: str = Form(""),
):
    SelfHostService.add_request(name, contact, comment)
    return redirect_with_flash(
        "/#pricing",
        "Заявка на self-hosting отправлена. Мы свяжемся с вами.",
        level="success",
    )