# -*- coding: utf-8 -*-
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.modules.auth.dependencies import get_current_user, get_current_user_id, require_authenticated
from app.modules.auth.models import User
from app.modules.subscriptions.dependencies import get_optional_subscription
from app.modules.subscriptions.models import Subscription, PLAN_LABELS
from app.modules.subscriptions.service import SubscriptionService
from app.shared.templating import templates
from app.modules.subscriptions.pricing import SUBSCRIPTION_PRICES, price_with_promo
from app.modules.subscriptions.service import PromoCodeService
from app.shared.flash import redirect_with_flash

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
            "is_admin": bool(current_user.is_admin),
        },
    )


@router.get("/subscribe")
async def subscribe_page(
    request: Request,
    promo: str = "",
    current_user: User = Depends(require_authenticated),
    subscription: Subscription | None = Depends(get_optional_subscription),
    db: AsyncSession = Depends(get_db)
):
    promo_data = await PromoCodeService.get_active_by_code(db, promo)
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
        return redirect_with_flash("/subscribe", "Неверный тариф подписки.", level="error")

    promo_data = await PromoCodeService.get_active_by_code(db, promo)
    if promo.strip() and promo_data is None:
        return redirect_with_flash("/subscribe", "Промокод не найден или недействителен.", level="error")

    final_price, _ = price_with_promo(SUBSCRIPTION_PRICES[plan], promo_data)
    await SubscriptionService.create_subscription(
        db,
        current_user.id,
        plan,
        promo_code=promo.strip().upper() if promo_data else None,
        price=final_price,
    )
    return redirect_with_flash("/account", "Подписка активирована.", level="success")

@router.post("/cancel-subscription")
async def cancel_subscription(
    request: Request,
    subscription_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user_id = await get_current_user_id(request)
    if user_id is None:
        return redirect_with_flash("/#register", "Сначала войдите в аккаунт.", level="error")

    await SubscriptionService.cancel_subscription(db, user_id, subscription_id)
    return redirect_with_flash("/account", "Подписка отменена.", level="info")