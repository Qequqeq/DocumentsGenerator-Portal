from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship  # ← добавь relationship

from app.shared.models import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")