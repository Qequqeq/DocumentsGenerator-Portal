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
from app.modules.blog.models import Article
from app.modules.blog.service import ArticleService, render_markdown
from app.modules.solutions.categories import CATEGORY_NAMES, SOLUTION_CATEGORIES
from app.modules.solutions.models import Solution
from app.modules.solutions.service import SolutionService
from app.shared.templating import templates
from app.modules.admin.security import ADMIN_COOKIE, check_admin_password, is_admin_unlocked, make_admin_cookie
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.subscriptions.models import PromoCode
from app.modules.subscriptions.service import PromoCodeService

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


def _article_form_context(request: Request, article=None, errors=None, values=None):
    return {
        "request": request,
        "article": article,
        "errors": errors or [],
        "values": values or {},
        "current_user_email": None,
    }


@router.get("/articles")
async def admin_articles_list(
    request: Request,
    status: str = "",
    q: str = "",
    saved: str = "",
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func as sa_func

    articles = await ArticleService.list_all(db, status=status, q=q)
    total = (await db.execute(select(sa_func.count(Article.id)))).scalar() or 0
    published = (
        await db.execute(
            select(sa_func.count(Article.id)).where(Article.is_published.is_(True))
        )
    ).scalar() or 0
    return templates.TemplateResponse(
        "admin_articles.html",
        {
            "request": request,
            "articles": articles,
            "status": status,
            "q": q,
            "saved": saved == "1",
            "counts": {"all": total, "published": published, "draft": total - published},
            "current_user_email": current_user.email,
        },
    )


@router.get("/articles/new")
async def admin_article_new(
    request: Request,
    current_user: User = Depends(require_admin),
):
    ctx = _article_form_context(request)
    ctx["current_user_email"] = current_user.email
    return templates.TemplateResponse("admin_article_form.html", ctx)


@router.get("/articles/{article_id}/edit")
async def admin_article_edit(
    request: Request,
    article_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    article = await db.get(Article, article_id)
    if article is None:
        return RedirectResponse(url="/admin/articles", status_code=303)
    ctx = _article_form_context(request, article=article)
    ctx["current_user_email"] = current_user.email
    return templates.TemplateResponse("admin_article_form.html", ctx)


@router.post("/articles/save")
async def admin_article_save(
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    article_id = (form.get("article_id") or "").strip()
    title = (form.get("title") or "").strip()
    annotation = (form.get("annotation") or "").strip()
    content_md = form.get("content_md") or ""
    is_published = form.get("is_published") == "on"

    errors = []
    if not title:
        errors.append("Укажите заголовок статьи.")
    if not content_md.strip():
        errors.append("Текст статьи пуст.")

    article = None
    if article_id:
        article = await db.get(Article, int(article_id))
        if article is None:
            errors.append("Статья не найдена.")

    if errors:
        ctx = _article_form_context(
            request,
            article=article,
            errors=errors,
            values={"title": title, "annotation": annotation, "content_md": content_md, "is_published": is_published},
        )
        ctx["current_user_email"] = current_user.email
        return templates.TemplateResponse("admin_article_form.html", ctx, status_code=400)

    if article is not None:
        await ArticleService.update_article(
            db, article,
            title=title, annotation=annotation, content_md=content_md, is_published=is_published,
        )
    else:
        await ArticleService.create_article(
            db,
            title=title, annotation=annotation, content_md=content_md, is_published=is_published,
        )
    return RedirectResponse(url="/admin/articles?saved=1", status_code=303)


@router.post("/articles/preview")
async def admin_article_preview(
    request: Request,
    current_user: User = Depends(require_admin),
):
    form = await request.form()
    title = (form.get("title") or "").strip() or "Без заголовка"
    annotation = (form.get("annotation") or "").strip()
    content_md = form.get("content_md") or ""
    return templates.TemplateResponse(
        "admin_article_preview.html",
        {
            "request": request,
            "title": title,
            "annotation": annotation,
            "content_html": render_markdown(content_md),
            "current_user_email": current_user.email,
        },
    )


@router.post("/articles/{article_id}/delete")
async def admin_article_delete(
    article_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    article = await db.get(Article, article_id)
    if article is not None:
        await ArticleService.delete_article(db, article)
    return RedirectResponse(url="/admin/articles?saved=1", status_code=303)


@router.get("/promos")
async def admin_promos_list(
    request: Request,
    saved: str = "",
    error: str = "",
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    promos = await PromoCodeService.list_all(db)
    return templates.TemplateResponse(
        "admin_promos.html",
        {
            "request": request,
            "promos": promos,
            "saved": saved == "1",
            "error": error,
            "current_user_email": current_user.email,
        },
    )


@router.post("/promos/save")
async def admin_promo_save(
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    promo_id = (form.get("promo_id") or "").strip()
    code = (form.get("code") or "").strip().upper()
    promo_type = (form.get("type") or "").strip()
    value_raw = (form.get("value") or "").strip()
    label = (form.get("label") or "").strip()
    is_active = form.get("is_active") == "on"

    if not code:
        return RedirectResponse(url="/admin/promos?error=code", status_code=303)
    if promo_type not in ("percent", "fixed"):
        return RedirectResponse(url="/admin/promos?error=type", status_code=303)
    try:
        value = int(value_raw)
        if value <= 0:
            raise ValueError
        if promo_type == "percent" and value > 100:
            return RedirectResponse(url="/admin/promos?error=percent", status_code=303)
    except ValueError:
        return RedirectResponse(url="/admin/promos?error=value", status_code=303)

    exclude_id = int(promo_id) if promo_id else None
    if await PromoCodeService.code_exists(db, code, exclude_id):
        return RedirectResponse(url="/admin/promos?error=exists", status_code=303)

    if exclude_id:
        promo = await db.get(PromoCode, exclude_id)
        if promo is None:
            return RedirectResponse(url="/admin/promos", status_code=303)
        await PromoCodeService.update(
            db, promo, code=code, type=promo_type, value=value, label=label, is_active=is_active
        )
    else:
        await PromoCodeService.create(db, code=code, type=promo_type, value=value, label=label)

    return RedirectResponse(url="/admin/promos?saved=1", status_code=303)


@router.post("/promos/{promo_id}/delete")
async def admin_promo_delete(
    promo_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    promo = await db.get(PromoCode, promo_id)
    if promo is not None:
        await PromoCodeService.delete(db, promo)
    return RedirectResponse(url="/admin/promos?saved=1", status_code=303)


@router.get("/admins")
async def admin_admins_list(
    request: Request,
    msg: str = "",
    error: str = "",
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = list((await db.execute(select(User).order_by(User.created_at))).scalars().all())
    return templates.TemplateResponse(
        "admin_admins.html",
        {
            "request": request,
            "users": users,
            "current_user": current_user,
            "msg": msg,
            "error": error,
            "current_user_email": current_user.email,
        },
    )


@router.post("/admins/add")
async def admin_admins_add(
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    email = (form.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return RedirectResponse(url="/admin/admins?error=empty", status_code=303)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return RedirectResponse(url=f"/admin/admins?error=not_found&msg={quote(email)}", status_code=303)
    if user.is_admin:
        return RedirectResponse(url="/admin/admins?error=already", status_code=303)

    user.is_admin = True
    await db.flush()
    return RedirectResponse(url="/admin/admins?msg=added", status_code=303)


@router.post("/admins/{user_id}/grant")
async def admin_admins_grant(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is not None and not user.is_admin:
        user.is_admin = True
        await db.flush()
    return RedirectResponse(url="/admin/admins?msg=added", status_code=303)


@router.post("/admins/{user_id}/revoke")
async def admin_admins_revoke(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if user_id == current_user.id:
        return RedirectResponse(url="/admin/admins?error=self", status_code=303)
    user = await db.get(User, user_id)
    if user is not None and user.is_admin:
        user.is_admin = False
        await db.flush()
    return RedirectResponse(url="/admin/admins?msg=revoked", status_code=303)