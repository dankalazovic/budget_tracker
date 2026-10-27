from __future__ import annotations

from datetime import date as DateValue
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.category import Category


class Transaction(db.Model):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(7), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False)
    date: Mapped[DateValue] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.id", name="fk_transaction_category", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    category: Mapped[Category] = relationship("Category", back_populates="transactions")

    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="ck_transaction_type"),
        CheckConstraint("amount > 0 AND amount <= 1000000", name="ck_transaction_amount"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "amount": format(self.amount, ".2f"),
            "date": self.date.isoformat(),
            "description": self.description,
            "category_id": self.category_id,
        }
