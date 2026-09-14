# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.blog.service import ArticleService, render_markdown
from app.shared.templating import templates

router = APIRouter()


@router.get("/blog")
async def blog_list(
    request: Request,
    msg: str = "",
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    articles = await ArticleService.list_published(db)
    return templates.TemplateResponse(
        "blog.html",
        {
            "request": request,
            "articles": articles,
            "msg": msg,
            "current_user_email": current_user.email if current_user else None,
        },
    )


@router.get("/blog/{slug}")
async def blog_article(
    request: Request,
    slug: str,
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    article = await ArticleService.get_by_slug(db, slug)
    if article is None or not article.is_published:
        return RedirectResponse(url="/blog?msg=not_found", status_code=303)
    return templates.TemplateResponse(
        "blog_article.html",
        {
            "request": request,
            "article": article,
            "content_html": render_markdown(article.content_md),
            "related": await ArticleService.related_articles(db, article.id),
            "current_user_email": current_user.email if current_user else None,
        },
    )