# -*- coding: utf-8 -*-
from datetime import timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.models import Subscription
from app.shared.timeutils import utcnow


class SubscriptionService:
    @staticmethod
    async def get_active_subscription(
        db: AsyncSession,
        user_id: int,
    ) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )
        subscription = result.scalar_one_or_none()

        if subscription is None:
            return None
        if subscription.expires_at < utcnow():
            subscription.status = "expired"
            await db.commit()
            return None

        return subscription

    @staticmethod
    async def create_subscription(
            db: AsyncSession,
            user_id: int,
            plan: str,
            promo_code: Optional[str] = None,
            price: Optional[int] = None,
    ) -> Subscription:
        await db.execute(
            update(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .values(status="superseded")
        )

        now = utcnow()
        if plan == "monthly":
            expires_at = now + timedelta(days=30)
        elif plan == "yearly":
            expires_at = now + timedelta(days=365)
        else:
            raise ValueError(f"Unknown plan: {plan}")

        subscription = Subscription(
            user_id=user_id,
            plan=plan,
            started_at=now,
            expires_at=expires_at,
            status="active",
            promo_code=promo_code,
            price=price,
        )
        db.add(subscription)
        await db.flush()
        await db.refresh(subscription)
        return subscription

    @staticmethod
    async def cancel_subscription(
            db: AsyncSession,
            user_id: int,
            subscription_id: int,
    ) -> bool:
        result = await db.execute(
            select(Subscription).where(
                Subscription.id == subscription_id,
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
        )
        subscription = result.scalar_one_or_none()

        if subscription is None:
            return False

        subscription.status = "cancelled"
        await db.commit()
        return True