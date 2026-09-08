# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.modules.landing.router import router as landing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="АвтоРиск",
        description="",
        version="0.1.0",
        lifespan=lifespan,
    )
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    # Подключаем роутеры
    from app.modules.landing.router import router as landing_router
    from app.modules.auth.router import router as auth_router
    from app.modules.subscriptions.router import router as subscriptions_router

    app.include_router(landing_router)
    app.include_router(auth_router)
    app.include_router(subscriptions_router)
    # TODO: в следующих шагах подключим остальные роутеры
    # from app.modules.subscriptions.router import router as subscriptions_router
    # app.include_router(subscriptions_router)
    # from app.modules.landing.router import router as landing_router
    # from app.modules.auth.router import router as auth_router
    # from app.modules.subscriptions.router import router as subscriptions_router
    # app.include_router(landing_router)
    # app.include_router(auth_router)
    # app.include_router(subscriptions_router)

    return app


app = create_app()