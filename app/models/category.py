from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.constants import ConstraintName, TEXT_COLUMN_LENGTH

if TYPE_CHECKING:
    from app.models.transaction import Transaction


class Category(db.Model):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(TEXT_COLUMN_LENGTH), nullable=False)
    color: Mapped[str] = mapped_column(String(TEXT_COLUMN_LENGTH), nullable=False)

    transactions: Mapped[list[Transaction]] = relationship(
        "Transaction", back_populates="category"
    )

    __table_args__ = (
        Index(ConstraintName.CATEGORY_NAME.value, func.lower(name), unique=True),
    )
