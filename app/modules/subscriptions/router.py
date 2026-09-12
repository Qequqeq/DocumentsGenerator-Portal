# -*- coding: utf-8 -*-
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.modules.auth.dependencies import get_current_user, get_current_user_id, require_authenticated
from app.modules.auth.models import User
from app.modules.subscriptions.dependencies import get_optional_subscription
from app.modules.subscriptions.models import Subscription, PLAN_LABELS
from app.modules.subscriptions.service import SubscriptionService
from app.shared.templating import templates
from app.modules.subscriptions.pricing import SUBSCRIPTION_PRICES, get_promo, price_with_promo

router = APIRouter()


@router.get("/account")
async def account_page(
    request: Request,
    msg: str = "",
    current_user: User = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
):
    subscription = await SubscriptionService.get_active_subscription(db, current_user.id)
    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "email": current_user.email,
            "created_at": current_user.created_at,
            "subscription": subscription,
            "plan_labels": PLAN_LABELS,
            "msg": msg,
            "current_user_email": current_user.email,
        },
    )


@router.get("/subscribe")
async def subscribe_page(
    request: Request,
    promo: str = "",
    current_user: User = Depends(require_authenticated),
    subscription: Subscription | None = Depends(get_optional_subscription),
):
    promo_data = get_promo(promo)
    prices = {}
    for plan, base in SUBSCRIPTION_PRICES.items():
        final, discount = price_with_promo(base, promo_data)
        prices[plan] = {"base": base, "final": final, "discount": discount}

    return templates.TemplateResponse(
        "subscribe.html",
        {
            "request": request,
            "subscription": subscription,
            "plan_labels": PLAN_LABELS,
            "promo_input": promo.strip().upper(),
            "promo_data": promo_data,
            "promo_invalid": bool(promo.strip()) and promo_data is None,
            "prices": prices,
            "current_user_email": current_user.email,
        },
    )


@router.post("/subscribe")
async def subscribe_create(
    plan: str = Form(...),
    promo: str = Form(""),
    current_user: User = Depends(require_authenticated),
    db: AsyncSession = Depends(get_db),
):
    if plan not in PLAN_LABELS:
        return RedirectResponse(url="/subscribe", status_code=303)

    promo_data = get_promo(promo)
    if promo.strip() and promo_data is None:
        return RedirectResponse(url=f"/subscribe?promo={quote(promo.strip().upper())}", status_code=303)

    final_price, _ = price_with_promo(SUBSCRIPTION_PRICES[plan], promo_data)
    await SubscriptionService.create_subscription(
        db,
        current_user.id,
        plan,
        promo_code=promo.strip().upper() if promo_data else None,
        price=final_price,
    )
    return RedirectResponse(url="/account?msg=sub_activated", status_code=303)

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