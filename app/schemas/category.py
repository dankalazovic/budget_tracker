from typing import Annotated

from pydantic import AfterValidator, Field, StrictStr, StringConstraints

from app.schemas.common import Schema, valid_text


class CategoryCreate(Schema):
    name: Annotated[
        StrictStr,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=30),
        AfterValidator(valid_text),
    ]
    color: Annotated[
        StrictStr, Field(min_length=7, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")
    ]


class CategoryResponse(Schema):
    id: int
    name: str
    color: str
