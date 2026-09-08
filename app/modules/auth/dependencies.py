# -*- coding: utf-8 -*-
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.models import User
from app.modules.auth.service import SessionService


async def get_current_user_id(request: Request) -> Optional[int]:
    cookie = request.cookies.get("session")
    return SessionService.parse_session_cookie(cookie)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    user_id = await get_current_user_id(request)
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()