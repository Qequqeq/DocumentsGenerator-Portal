# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.modules.landing.router import router as landing_router

from fastapi import Request
from fastapi.responses import RedirectResponse
from app.shared.exceptions import RedirectException

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

    @app.exception_handler(RedirectException)
    async def redirect_exception_handler(request: Request, exc: RedirectException):
        return RedirectResponse(url=exc.url, status_code=exc.status_code)

    settings.static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    # Подключаем роутеры
    from app.modules.landing.router import router as landing_router
    from app.modules.auth.router import router as auth_router
    from app.modules.subscriptions.router import router as subscriptions_router
    from app.modules.projects.router import router as projects_router
    from app.modules.settings.router import router as settings_router
    from app.modules.templates.router import router as templates_router

    app.include_router(landing_router)
    app.include_router(auth_router)
    app.include_router(subscriptions_router)
    app.include_router(projects_router)
    app.include_router(settings_router)
    app.include_router(templates_router)
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