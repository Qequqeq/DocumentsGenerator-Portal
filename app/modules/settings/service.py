# -*- coding: utf-8 -*-
import copy
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.settings.defaults import DEFAULTS
from app.modules.settings.models import UserCustomization

# Типы ключей для каждой секции: JSON хранит ключи строками,
# поэтому при чтении/записи приводим их к исходному типу.
SECTION_KEY_TYPES = {
    "DEGREE_INFO": int,
    "CHANCE_INFO": int,
    "COEFF_INFO": float,
    "CONTROL_INFO": str,
    "SUMMARY_INFO": float,
    "SUMMARY_INFO_APLICATION": float,
    "MANAGEMENT_MEASURES": str,
}


def _cast_keys(section: str, data: Any) -> Dict:
    caster = SECTION_KEY_TYPES.get(section)
    if caster is None or not isinstance(data, dict):
        return data or {}
    result = {}
    for key, value in data.items():
        try:
            result[caster(key)] = value
        except (TypeError, ValueError):
            continue
    return result


class CustomizationService:
    @staticmethod
    async def _get_or_create(db: AsyncSession, user_id: int) -> UserCustomization:
        result = await db.execute(
            select(UserCustomization).where(UserCustomization.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = UserCustomization(user_id=user_id, data={})
            db.add(row)
            await db.flush()
        return row

    @staticmethod
    async def get_effective(db: AsyncSession, user_id: int) -> Dict[str, Any]:
        row = await CustomizationService._get_or_create(db, user_id)
        effective = copy.deepcopy(DEFAULTS)
        for section, values in (row.data or {}).items():
            effective[section] = _cast_keys(section, values)
        return effective

    @staticmethod
    async def save_section(
        db: AsyncSession,
        user_id: int,
        section: str,
        values: Dict,
    ) -> None:
        row = await CustomizationService._get_or_create(db, user_id)
        data = dict(row.data or {})
        data[section] = _cast_keys(section, values)
        row.data = data
        await db.flush()

    @staticmethod
    async def reset_section(db: AsyncSession, user_id: int, section: str) -> None:
        row = await CustomizationService._get_or_create(db, user_id)
        data = dict(row.data or {})
        data.pop(section, None)
        row.data = data
        await db.flush()

    @staticmethod
    async def get_measures(db: AsyncSession, user_id: int) -> Dict[str, List[str]]:
        from app.modules.settings.risk_catalog import RISK_DATABASE

        effective = await CustomizationService.get_effective(db, user_id)
        overrides = effective.get("MANAGEMENT_MEASURES", {}) or {}
        measures = {}
        for risk_number, risk in RISK_DATABASE.items():
            default = list(getattr(risk, "management_measures", None) or [])
            measures[risk_number] = overrides.get(risk_number, default)
        return measures