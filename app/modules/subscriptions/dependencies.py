# -*- coding: utf-8 -*-
from typing import Optional

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.dependencies import get_current_user_id
from app.modules.subscriptions.models import Subscription
from app.modules.subscriptions.service import SubscriptionService
from app.shared.exceptions import RedirectException


async def get_optional_subscription(
    user_id: Optional[int] = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Optional[Subscription]:
    if user_id is None:
        return None
    return await SubscriptionService.get_active_subscription(db, user_id)

async def require_subscription(
    subscription: Subscription | None = Depends(get_optional_subscription),
) -> Subscription:
    if subscription is None:
        raise RedirectException("/subscribe")
    return subscription