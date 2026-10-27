from datetime import date
from decimal import Decimal

from pydantic import field_serializer

from app.schemas.common import Month, Schema


class SummaryQuery(Schema):
    month: Month


class CategorySummary(Schema):
    category_id: int
    category_name: str
    spent: Decimal
    budget: Decimal
    remaining: Decimal

    @field_serializer("spent", "budget", "remaining")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, ".2f")


class MonthlySummaryResponse(Schema):
    month: date
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal
    categories: list[CategorySummary]

    @field_serializer("month")
    def serialize_month(self, value: date) -> str:
        return value.isoformat()[:7]

    @field_serializer("total_income", "total_expense", "balance")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, ".2f")
