# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.templates.models import CustomTemplate


ALLOWED_KINDS = {
    "card": "card_template.docx",
    "report": "report_template.docx",
}

MAX_SIZE = 5 * 1024 * 1024  # 5 МБ


class TemplateService:
    @staticmethod
    def default_path(kind: str) -> Path:
        return get_settings().defaults_dir / ALLOWED_KINDS[kind]

    @staticmethod
    def _user_templates_dir(user_id: int) -> Path:
        d = get_settings().base_dir / "uploads" / str(user_id) / "templates"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    async def get_custom(
        db: AsyncSession,
        user_id: int,
        kind: str,
    ) -> Optional[CustomTemplate]:
        result = await db.execute(
            select(CustomTemplate).where(
                CustomTemplate.user_id == user_id,
                CustomTemplate.kind == kind,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def custom_absolute(row: CustomTemplate) -> Path:
        return get_settings().base_dir / "uploads" / str(row.user_id) / row.file_path

    @staticmethod
    async def resolve(
        db: AsyncSession,
        user_id: int,
        kind: str,
        is_premium: bool,
    ) -> Path:
        row = await TemplateService.get_custom(db, user_id, kind)
        if row is not None and is_premium:
            path = TemplateService.custom_absolute(row)
            if path.exists():
                return path
        return TemplateService.default_path(kind)

    @staticmethod
    async def save_custom(
        db: AsyncSession,
        user_id: int,
        kind: str,
        file: UploadFile,
    ) -> str:
        name = file.filename or ""
        if not name.lower().endswith(".docx"):
            return "docx"
        content = await file.read()
        if len(content) > MAX_SIZE:
            return "size"

        rel_path = f"templates/{kind}.docx"
        dest = TemplateService._user_templates_dir(user_id) / f"{kind}.docx"
        dest.write_bytes(content)

        row = await TemplateService.get_custom(db, user_id, kind)
        if row is None:
            row = CustomTemplate(
                user_id=user_id,
                kind=kind,
                original_name=name,
                file_path=rel_path,
            )
            db.add(row)
        else:
            row.original_name = name
            row.file_path = rel_path
        await db.flush()
        return ""

    @staticmethod
    async def delete_custom(db: AsyncSession, user_id: int, kind: str) -> None:
        row = await TemplateService.get_custom(db, user_id, kind)
        if row is None:
            return
        path = TemplateService.custom_absolute(row)
        if path.exists():
            path.unlink()
        await db.delete(row)
        await db.flush()