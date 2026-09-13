# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.solutions.categories import CATEGORY_NAMES, SOLUTION_CATEGORIES, category_name
from app.modules.solutions.service import SolutionService
from app.shared.templating import templates
from fastapi.responses import FileResponse, RedirectResponse


router = APIRouter()

RU_ALPHABET = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЭЮЯ"
PER_PAGE = 24


@router.get("/solutions")
async def solutions_catalog(
    request: Request,
    q: str = "",
    cat: str = "",
    letter: str = "",
    page: int = 1,
    project: str = "",
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = max(1, page)
    solutions, total = await SolutionService.list_published(
        db, q=q, category=cat, letter=letter, page=page, per_page=PER_PAGE
    )
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    available_letters = await SolutionService.available_letters(db)

    return templates.TemplateResponse(
        "solutions.html",
        {
            "request": request,
            "solutions": solutions,
            "categories": SOLUTION_CATEGORIES,
            "category_names": CATEGORY_NAMES,
            "q": q,
            "cat": cat,
            "letter": letter.upper() if letter else "",
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "available_letters": available_letters,
            "alphabet": RU_ALPHABET,
            "project": project,
            "current_user_email": current_user.email if current_user else None,
        },
    )

@router.get("/solutions/{slug}")
async def solution_detail(
    request: Request,
    slug: str,
    project: str = "",
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    solution = await SolutionService.get_by_slug(db, slug)
    if solution is None or not solution.is_published:
        return RedirectResponse(url="/solutions?msg=not_found", status_code=303)

    return templates.TemplateResponse(
        "solution_detail.html",
        {
            "request": request,
            "solution": solution,
            "category_name": category_name(solution.category),
            "preview": SolutionService.build_preview(solution),
            "project": project,
            "current_user_email": current_user.email if current_user else None,
        },
    )


@router.get("/solutions/{slug}/pdf")
async def solution_pdf(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    solution = await SolutionService.get_by_slug(db, slug)
    if solution is None or not solution.is_published or not solution.sample_pdf_path:
        raise HTTPException(status_code=404, detail="PDF не найден")
    path = SolutionService.solutions_dir() / solution.sample_pdf_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF не найден")
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )