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