# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_name: Optional[str]
    doc_date: Optional[str]
    status: str
    workers_count: int
    generated_count: int
    created_at: datetime
    updated_at: datetime

    @property
    def status_label(self) -> str:
        labels = {
            "draft": "Черновик",
            "in_progress": "В работе",
            "completed": "Завершён",
            "paid": "Оплачен",
        }
        return labels.get(self.status, self.status)

    @property
    def status_class(self) -> str:
        classes = {
            "draft": "bg-gray-100 text-gray-600",
            "in_progress": "bg-blue-100 text-blue-700",
            "completed": "bg-green-100 text-green-700",
            "paid": "bg-indigo-100 text-indigo-700",
        }
        return classes.get(self.status, "bg-gray-100 text-gray-600")


class ProjectCreate(BaseModel):
    org_name: Optional[str] = None
    doc_date: Optional[str] = None


ORG_SCALAR_FIELDS = {
    "full_name": "Полное наименование организации",
    "short_name": "Сокращенное наименование организации",
    "kpp": "Код причины постановки на учет (КПП)",
    "inn": "Идентификационный номер налогоплательщика (ИНН)",
    "okpo": "Код работодателя по ОКПО",
    "okogy": "Код органа государственной власти по ОКОГУ",
    "okved": "Код основного вида экономической деятельности работодателя ОКВЭД",
    "oktmo": "Код территории по ОКТМО",
    "address": "Юридический адрес организации",
    "auditor_pos": "Аудитор (должность)",
    "auditor_name": "Аудитор (Ф.И.О. полностью)",
    "leader_pos": "Руководитель организации (должность)",
    "leader_name": "Руководитель организации (Ф.И.О. полностью)",
    "chairman_pos": "Председатель рабочей группы по проведению оценки профессиональных рисков (должность)",
    "chairman_name": "Председатель рабочей группы по проведению оценки профессиональных рисков (Ф.И.О. полностью)",
}

ORG_LIST_FIELDS = {
    "chairmen_poses": "Члены рабочей группы по проведению оценки профессиональных рисков (должность)",
    "chairmen_names": "Члены рабочей группы по проведению оценки профессиональных рисков (Ф.И.О. полностью)",
}