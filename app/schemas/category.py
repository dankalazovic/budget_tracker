from typing import Annotated

from pydantic import Field, StrictStr

from app.schemas.common import CategoryName, Schema


class CategoryCreate(Schema):
    name: CategoryName
    color: Annotated[
        StrictStr, Field(min_length=7, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")
    ]


class CategoryResponse(Schema):
    id: int
    name: str
    color: str
