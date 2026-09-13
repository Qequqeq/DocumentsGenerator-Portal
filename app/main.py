# -*- coding: utf-8 -*-
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db

from fastapi import Request
from fastapi.responses import RedirectResponse
from app.shared.exceptions import RedirectException

from app.database import AsyncSessionLocal, init_db


async def promote_admin() -> None:
    settings = get_settings()
    if not settings.admin_email:
        return
    from sqlalchemy import update as sa_update
    from app.modules.auth.models import User

    async with AsyncSessionLocal() as session:
        await session.execute(
            sa_update(User)
            .where(User.email == settings.admin_email)
            .values(is_admin=True)
        )
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await promote_admin()
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

    from app.modules.landing.router import router as landing_router
    from app.modules.auth.router import router as auth_router
    from app.modules.subscriptions.router import router as subscriptions_router
    from app.modules.projects.router import router as projects_router
    from app.modules.settings.router import router as settings_router
    from app.modules.templates.router import router as templates_router
    from app.modules.admin.router import router as admin_router
    from app.modules.solutions.router import router as solutions_router
    from app.modules.blog.router import router as blog_router

    app.include_router(landing_router, tags=["landing"])
    app.include_router(auth_router, tags=["authentication"])
    app.include_router(subscriptions_router, tags=["subscription"])
    app.include_router(projects_router, tags=["project"])
    app.include_router(settings_router, tags=["settings"])
    app.include_router(templates_router, tags=["templates"])
    app.include_router(admin_router, tags=["admin"])
    app.include_router(solutions_router, tags=["solutions"])
    app.include_router(blog_router, tags=["blog"])

    return app


app = create_app()