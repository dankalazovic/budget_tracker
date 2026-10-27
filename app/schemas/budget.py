from datetime import date
from decimal import Decimal

from pydantic import field_serializer

from app.schemas.common import Amount, Month, Schema


class BudgetMonth(Schema):
    month: Month


class BudgetInput(Schema):
    amount: Amount


class BudgetResponse(Schema):
    id: int
    month: date
    category_id: int
    amount: Decimal

    @field_serializer("month")
    def serialize_month(self, value: date) -> str:
        return value.isoformat()[:7]

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, ".2f")
