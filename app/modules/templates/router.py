# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.dependencies import require_authenticated
from app.modules.auth.models import User
from app.modules.subscriptions.dependencies import get_optional_subscription, require_subscription
from app.modules.subscriptions.models import Subscription
from app.modules.templates.service import ALLOWED_KINDS, TemplateService
from app.shared.flash import redirect_with_flash
from app.shared.templating import templates

router = APIRouter()

ERROR_MESSAGES = {
    "docx": "Можно загрузить только файл .docx.",
    "size": "Файл слишком большой (максимум 5 МБ).",
    "bad_kind": "Неизвестный тип шаблона.",
}


@router.get("/settings/templates")
async def templates_page(
    request: Request,
    current_user: User = Depends(require_authenticated),
    subscription: Subscription | None = Depends(get_optional_subscription),
    db: AsyncSession = Depends(get_db),
    saved: str = "",
    error: str = "",
):
    custom_card = await TemplateService.get_custom(db, current_user.id, "card")
    custom_report = await TemplateService.get_custom(db, current_user.id, "report")
    return templates.TemplateResponse(
        "settings_templates.html",
        {
            "request": request,
            "is_premium": subscription is not None,
            "custom_card": custom_card,
            "custom_report": custom_report,
            "default_card_exists": TemplateService.default_path("card").exists(),
            "default_report_exists": TemplateService.default_path("report").exists(),
            "saved": saved == "1",
            "error": ERROR_MESSAGES.get(error, ""),
            "current_user_email": current_user.email,
        },
    )


@router.post("/settings/templates/upload")
async def templates_upload(
    kind: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    if kind not in ALLOWED_KINDS:
        return redirect_with_flash("/settings/templates", ERROR_MESSAGES.get("bad_kind", "Неизвестный тип шаблона."), level="error")
    error_code = await TemplateService.save_custom(db, current_user.id, kind, file)
    if error_code:
        return redirect_with_flash("/settings/templates", ERROR_MESSAGES.get(error_code, "Ошибка загрузки шаблона."), level="error")
    return redirect_with_flash("/settings/templates", "Шаблон успешно загружен.", level="success")


@router.post("/settings/templates/delete")
async def templates_delete(
    kind: str = Form(...),
    current_user: User = Depends(require_authenticated),
    subscription: Subscription = Depends(require_subscription),
    db: AsyncSession = Depends(get_db),
):
    if kind in ALLOWED_KINDS:
        await TemplateService.delete_custom(db, current_user.id, kind)
    return redirect_with_flash("/settings/templates", "Шаблон удалён. Возвращены стандартные настройки.", level="info")