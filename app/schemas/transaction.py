from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import Field, field_serializer, field_validator, model_validator
from app.constants import DEFAULT_PAGE_SIZE, ErrorMessage, MAX_PAGE_SIZE

from app.schemas.common import (
    MAX_DATABASE_ID,
    Amount,
    CalendarDate,
    CleanText,
    DatabaseID,
    QueryInteger,
    Schema,
)


class TransactionType(str, Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionInput(Schema):
    type: TransactionType
    amount: Amount
    date: CalendarDate
    category_id: DatabaseID
    description: Annotated[CleanText, Field(max_length=200)] | None = None

    @field_validator("description")
    @classmethod
    def empty_description(cls, value):
        return None if value == "" else value


class TransactionResponse(Schema):
    id: int
    type: TransactionType
    amount: Decimal
    date: date
    description: str | None
    category_id: int

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, ".2f")


class TransactionListResponse(Schema):
    items: list[TransactionResponse]
    page: int
    per_page: int
    total: int
    pages: int


class TransactionFilters(Schema):
    date_from: CalendarDate | None = None
    date_to: CalendarDate | None = None
    category_id: Annotated[QueryInteger, Field(gt=0, le=MAX_DATABASE_ID)] | None = None
    type: TransactionType | None = None
    search: CleanText | None = None
    page: Annotated[QueryInteger, Field(gt=0, le=MAX_DATABASE_ID)] = 1
    per_page: Annotated[QueryInteger, Field(gt=0, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.date_from is not None and self.date_to is not None:
            if self.date_from > self.date_to:
                raise ValueError(ErrorMessage.DATE_RANGE)
        return self
