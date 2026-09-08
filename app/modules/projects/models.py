# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import Base, TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    org_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    doc_date: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )
    workers_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    generated_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    card_template_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    rep_template_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    people_file_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    org_file_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    people_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    org_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    risk_inputs: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    generated_cards: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
    )
    user = relationship("User", back_populates="projects")

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