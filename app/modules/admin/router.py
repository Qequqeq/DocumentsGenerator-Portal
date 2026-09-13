# -*- coding: utf-8 -*-
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.modules.admin.security import ADMIN_COOKIE
from app.modules.auth.dependencies import require_admin, require_authenticated
from app.modules.auth.models import User
from app.modules.solutions.categories import CATEGORY_NAMES, SOLUTION_CATEGORIES
from app.modules.solutions.models import Solution
from app.modules.solutions.service import SolutionService
from app.shared.templating import templates
from app.modules.admin.security import ADMIN_COOKIE, check_admin_password, is_admin_unlocked, make_admin_cookie

router = APIRouter(prefix="/admin")


def _form_context(request: Request, solution=None, errors=None, values=None):
    return {
        "request": request,
        "solution": solution,
        "categories": SOLUTION_CATEGORIES,
        "errors": errors or [],
        "values": values or {},
    }


@router.get("/solutions")
async def admin_solutions_list(
    request: Request,
    status: str = "",
    q: str = "",
    saved: str = "",
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    solutions = await SolutionService.list_solutions(db, status=status, q=q)
    total = (await db.execute(select(func.count(Solution.id)))).scalar() or 0
    published = (
        await db.execute(
            select(func.count(Solution.id)).where(Solution.is_published.is_(True))
        )
    ).scalar() or 0
    return templates.TemplateResponse(
        "admin_solutions.html",
        {
            "request": request,
            "solutions": solutions,
            "category_names": CATEGORY_NAMES,
            "status": status,
            "q": q,
            "saved": saved == "1",
            "counts": {"all": total, "published": published, "draft": total - published},
            "current_user_email": current_user.email,
        },
    )


@router.get("/solutions/new")
async def admin_solution_new(
    request: Request,
    current_user: User = Depends(require_admin),
):
    return templates.TemplateResponse("admin_solution_form.html", _form_context(request))


@router.get("/solutions/{solution_id}/edit")
async def admin_solution_edit(
    request: Request,
    solution_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    solution = await db.get(Solution, solution_id)
    if solution is None:
        return RedirectResponse(url="/admin/solutions", status_code=303)
    return templates.TemplateResponse(
        "admin_solution_form.html",
        _form_context(request, solution=solution),
    )


@router.post("/solutions/save")
async def admin_solution_save(
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    solution_id = (form.get("solution_id") or "").strip()
    position = (form.get("position") or "").strip()
    category = (form.get("category") or "").strip()
    description = (form.get("description") or "").strip()
    detailed_description = (form.get("detailed_description") or "").strip()
    is_published = form.get("is_published") == "on"

    json_file = form.get("json_file")
    pdf_file = form.get("pdf_file")

    errors = []
    if not position:
        errors.append("Укажите должность.")
    if category not in CATEGORY_NAMES:
        errors.append("Выберите категорию.")

    json_bytes = None
    if json_file is not None and getattr(json_file, "filename", ""):
        json_bytes = await json_file.read()
        try:
            data = json.loads(json_bytes)
            if not isinstance(data.get("risks"), dict):
                raise ValueError("missing risks")
        except Exception:
            errors.append("Файл шаблона должен быть корректным JSON с полем «risks».")
            json_bytes = None

    pdf_bytes = None
    if pdf_file is not None and getattr(pdf_file, "filename", ""):
        if not (pdf_file.filename or "").lower().endswith(".pdf"):
            errors.append("Пример карты должен быть файлом .pdf.")
        else:
            pdf_bytes = await pdf_file.read()

    solution = None
    if solution_id:
        solution = await db.get(Solution, int(solution_id))
        if solution is None:
            errors.append("Решение не найдено.")
    elif json_bytes is None:
        errors.append("При создании решения файл .json обязателен.")

    if errors:
        values = {
            "position": position,
            "category": category,
            "description": description,
            "detailed_description": detailed_description,
            "is_published": is_published,
        }
        return templates.TemplateResponse(
            "admin_solution_form.html",
            _form_context(request, solution=solution, errors=errors, values=values),
            status_code=400,
        )

    if solution is not None:
        await SolutionService.update_solution(
            db,
            solution,
            position=position,
            category=category,
            description=description,
            detailed_description=detailed_description,
            is_published=is_published,
            json_bytes=json_bytes,
            pdf_bytes=pdf_bytes,
        )
    else:
        await SolutionService.create_solution(
            db,
            position=position,
            category=category,
            description=description,
            detailed_description=detailed_description,
            is_published=is_published,
            json_bytes=json_bytes,
            pdf_bytes=pdf_bytes,
        )

    return RedirectResponse(url="/admin/solutions?saved=1", status_code=303)


@router.post("/solutions/{solution_id}/delete")
async def admin_solution_delete(
    solution_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    solution = await db.get(Solution, solution_id)
    if solution is not None:
        await SolutionService.delete_solution(db, solution)
    return RedirectResponse(url="/admin/solutions?saved=1", status_code=303)

@router.get("/unlock")
async def admin_unlock_page(
    request: Request,
    error: str = "",
    current_user: User = Depends(require_authenticated),
):
    if not getattr(current_user, "is_admin", False):
        return RedirectResponse(url="/account", status_code=303)
    if is_admin_unlocked(request):
        return RedirectResponse(url="/admin/solutions", status_code=303)
    return templates.TemplateResponse(
        "admin_unlock.html",
        {
            "request": request,
            "error": error == "invalid",
            "password_unset": not get_settings().admin_password,
            "current_user_email": current_user.email,
        },
    )


@router.post("/unlock")
async def admin_unlock(
    request: Request,
    password: str = Form(...),
    current_user: User = Depends(require_authenticated),
):
    if not getattr(current_user, "is_admin", False):
        return RedirectResponse(url="/account", status_code=303)
    if not check_admin_password(password):
        return RedirectResponse(url="/admin/unlock?error=invalid", status_code=303)

    value, max_age = make_admin_cookie()
    response = RedirectResponse(url="/admin/solutions", status_code=303)
    response.set_cookie(
        ADMIN_COOKIE,
        value,
        httponly=True,
        samesite="lax",
        max_age=max_age,
    )
    return response


@router.get("/lock")
async def admin_lock():
    response = RedirectResponse(url="/account", status_code=303)
    response.delete_cookie(ADMIN_COOKIE)
    return response