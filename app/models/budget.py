from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import ConstraintName
from app.extensions import db

if TYPE_CHECKING:
    from app.models.category import Category


class Budget(db.Model):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.id", name=ConstraintName.BUDGET_CATEGORY.value, ondelete="CASCADE"),
        nullable=False,
    )

    category: Mapped[Category] = relationship("Category")

    __table_args__ = (
        UniqueConstraint("category_id", "month", name=ConstraintName.BUDGET_CATEGORY_MONTH.value),
    )
