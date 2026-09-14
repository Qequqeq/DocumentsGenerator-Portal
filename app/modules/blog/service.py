# -*- coding: utf-8 -*-
import re
from typing import List, Optional

import bleach
import markdown as md_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blog.models import Article
from app.shared.text import safe_filename, translit
from app.shared.timeutils import utcnow
import random

ALLOWED_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "pre", "code",
    "table", "thead", "tbody", "tr", "th", "td",
    "hr", "br", "strong", "em", "a", "img",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title"],
}


def render_markdown(text: str) -> str:
    """Markdown → безопасный HTML (сырой HTML/JS вырезается)."""
    html = md_lib.markdown(
        text or "",
        extensions=["fenced_code", "tables", "sane_lists"],
    )
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )


class ArticleService:
    @staticmethod
    def _base_slug(title: str) -> str:
        base = translit(title).lower().replace(" ", "-")
        base = safe_filename(base)
        base = re.sub(r"\.+", "-", base)
        base = re.sub(r"-+", "-", base).strip("-")
        return base or "article"

    @staticmethod
    async def ensure_unique_slug(db: AsyncSession, title: str, exclude_id: Optional[int] = None) -> str:
        base = ArticleService._base_slug(title)
        slug = base
        n = 2
        while True:
            stmt = select(Article.id).where(Article.slug == slug)
            if exclude_id is not None:
                stmt = stmt.where(Article.id != exclude_id)
            res = await db.execute(stmt)
            if res.scalar_one_or_none() is None:
                return slug
            slug = f"{base}-{n}"
            n += 1

    @staticmethod
    async def list_published(db: AsyncSession) -> List[Article]:
        stmt = (
            select(Article)
            .where(Article.is_published.is_(True))
            .order_by(Article.published_at.desc())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def list_all(db: AsyncSession, status: str = "", q: str = "") -> List[Article]:
        stmt = select(Article).order_by(Article.created_at.desc())
        if status == "published":
            stmt = stmt.where(Article.is_published.is_(True))
        elif status == "draft":
            stmt = stmt.where(Article.is_published.is_(False))
        if q:
            stmt = stmt.where(Article.title.ilike(f"%{q}%"))
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_by_slug(db: AsyncSession, slug: str) -> Optional[Article]:
        stmt = select(Article).where(Article.slug == slug)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def create_article(
        db: AsyncSession,
        *,
        title: str,
        annotation: str,
        content_md: str,
        is_published: bool,
    ) -> Article:
        article = Article(
            slug=await ArticleService.ensure_unique_slug(db, title),
            title=title,
            annotation=annotation,
            content_md=content_md,
            is_published=is_published,
            published_at=utcnow() if is_published else None,
        )
        db.add(article)
        await db.flush()
        await db.refresh(article)
        return article

    @staticmethod
    async def update_article(
        db: AsyncSession,
        article: Article,
        *,
        title: str,
        annotation: str,
        content_md: str,
        is_published: bool,
    ) -> Article:
        article.title = title
        article.annotation = annotation
        article.content_md = content_md
        article.is_published = is_published
        if is_published and article.published_at is None:
            article.published_at = utcnow()
        if not is_published:
            article.published_at = None
        await db.flush()
        await db.refresh(article)
        return article

    @staticmethod
    async def related_articles(
        db: AsyncSession,
        exclude_id: int,
        limit: int = 3,
    ) -> List[Article]:
        stmt = (
            select(Article)
            .where(
                Article.is_published.is_(True),
                Article.id != exclude_id,
            )
            .order_by(Article.published_at.desc())
        )
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())
        if not candidates:
            return []
        return random.sample(candidates, min(limit, len(candidates)))

    @staticmethod
    async def delete_article(db: AsyncSession, article: Article) -> None:
        await db.delete(article)
        await db.flush()