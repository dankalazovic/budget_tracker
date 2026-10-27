from __future__ import annotations

from datetime import date as DateValue
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.constants import ConstraintName, DESCRIPTION_COLUMN_LENGTH, TEXT_COLUMN_LENGTH

if TYPE_CHECKING:
    from app.models.category import Category


class Transaction(db.Model):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(TEXT_COLUMN_LENGTH), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False)
    date: Mapped[DateValue] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(DESCRIPTION_COLUMN_LENGTH), nullable=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.id", name=ConstraintName.TRANSACTION_CATEGORY.value, ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    category: Mapped[Category] = relationship("Category", back_populates="transactions")
