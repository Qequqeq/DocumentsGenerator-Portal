# -*- coding: utf-8 -*-
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def get_engine() -> AsyncEngine:
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_async_engine(
        settings.database_url,
        echo=settings.is_dev,
        connect_args=connect_args,
        future=True,
    )


engine: AsyncEngine = get_engine()
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    from app.shared.models import Base  # noqa: F401
    from app.modules.auth.models import User  # noqa: F401
    from app.modules.subscriptions.models import Subscription  # noqa: F401
    from app.modules.projects.models import Project  # noqa: F401
    from app.modules.settings.models import UserCustomization  # noqa: F401
    from app.modules.templates.models import CustomTemplate  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)