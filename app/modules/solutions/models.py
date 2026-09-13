# -*- coding: utf-8 -*-
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base, TimestampMixin


class Solution(TimestampMixin, Base):

    __tablename__ = "solutions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    detailed_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    template_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sample_pdf_path: Mapped[str] = mapped_column(String(500), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)