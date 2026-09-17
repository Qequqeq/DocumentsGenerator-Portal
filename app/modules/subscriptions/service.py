# -*- coding: utf-8 -*-
from datetime import timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.subscriptions.models import Subscription, PromoCode
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

class PromoCodeService:

    @staticmethod
    async def get_active_by_code(db: AsyncSession, code: str):
        if not code:
            return None
        result = await db.execute(
            select(PromoCode).where(
                PromoCode.code == code.strip().upper(),
                PromoCode.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(db: AsyncSession):
        result = await db.execute(select(PromoCode).order_by(PromoCode.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def code_exists(db: AsyncSession, code: str, exclude_id=None) -> bool:
        stmt = select(PromoCode.id).where(PromoCode.code == code)
        if exclude_id is not None:
            stmt = stmt.where(PromoCode.id != exclude_id)
        return (await db.execute(stmt)).scalar_one_or_none() is not None

    @staticmethod
    async def create(db: AsyncSession, *, code: str, type: str, value: int, label: str) -> PromoCode:
        promo = PromoCode(
            code=code.strip().upper(),
            type=type,
            value=value,
            label=label.strip(),
            is_active=True,
        )
        db.add(promo)
        await db.flush()
        await db.refresh(promo)
        return promo

    @staticmethod
    async def update(
        db: AsyncSession,
        promo: PromoCode,
        *,
        code: str,
        type: str,
        value: int,
        label: str,
        is_active: bool,
    ) -> PromoCode:
        promo.code = code.strip().upper()
        promo.type = type
        promo.value = value
        promo.label = label.strip()
        promo.is_active = is_active
        await db.flush()
        await db.refresh(promo)
        return promo

    @staticmethod
    async def delete(db: AsyncSession, promo: PromoCode) -> None:
        await db.delete(promo)
        await db.flush()