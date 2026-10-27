import re
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
)

from app.constants import ErrorMessage


MAX_DATABASE_ID = 2147483647


class Schema(BaseModel):
    model_config = ConfigDict(
        extra="ignore", from_attributes=True, use_enum_values=True
    )


def valid_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError(ErrorMessage.INVALID_TEXT)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(ErrorMessage.INVALID_TEXT) from None
    return value


def amount_string(value):
    if isinstance(value, str) and not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError(ErrorMessage.INVALID_AMOUNT)
    return value


def two_decimal_places(value: Decimal) -> Decimal:
    # Pydantic decimal_places zanemaruje zavrsne nule; nas ugovor je stroziji.
    if value.as_tuple().exponent < -2:
        raise ValueError(ErrorMessage.AMOUNT_DECIMAL_PLACES)
    return value


def calendar_date(value):
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(ErrorMessage.DATE_FORMAT)
    return value


def query_integer(value):
    if isinstance(value, str):
        if not re.fullmatch(r"[0-9]+", value):
            raise ValueError(ErrorMessage.POSITIVE_INTEGER)
        return int(value)
    return value


CleanText = Annotated[StrictStr, AfterValidator(valid_text)]
DatabaseID = Annotated[StrictInt, Field(gt=0, le=MAX_DATABASE_ID)]
QueryInteger = Annotated[StrictInt, BeforeValidator(query_integer)]
CalendarDate = Annotated[date, BeforeValidator(calendar_date)]
Amount = Annotated[
    Decimal,
    Field(gt=0, le=Decimal("1000000"), allow_inf_nan=False),
    BeforeValidator(amount_string),
    AfterValidator(two_decimal_places),
]
