# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.dependencies import get_current_user, get_current_user_id
from app.modules.auth.models import User
from app.modules.subscriptions.models import Subscription, PLAN_LABELS
from app.modules.subscriptions.service import SubscriptionService
from app.shared.templating import templates

router = APIRouter()


@router.get("/account")
async def account_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)

    subscription = await SubscriptionService.get_active_subscription(db, user_id)

    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "email": current_user.email if current_user else "",
            "created_at": current_user.created_at if current_user else None,
            "subscription": subscription,
            "plan_labels": PLAN_LABELS,
            "current_user_email": current_user.email if current_user else None,
        },
    )


@router.get("/subscribe")
async def subscribe_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)

    subscription = await SubscriptionService.get_active_subscription(db, user_id)

    return templates.TemplateResponse(
        "subscribe.html",
        {
            "request": request,
            "subscription": subscription,
            "plan_labels": PLAN_LABELS,
            "current_user_email": current_user.email if current_user else None,
        },
    )


@router.post("/subscribe")
async def subscribe_create(
    request: Request,
    plan: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)

    if plan not in PLAN_LABELS:
        return RedirectResponse(url="/subscribe", status_code=303)

    await SubscriptionService.create_subscription(db, user_id, plan)
    return RedirectResponse(url="/account", status_code=303)

@router.post("/cancel-subscription")
async def cancel_subscription(
    request: Request,
    subscription_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/#register", status_code=303)

    await SubscriptionService.cancel_subscription(db, user_id, subscription_id)
    return RedirectResponse(url="/account", status_code=303)