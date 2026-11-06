from enum import StrEnum

from pydantic import BaseModel

from libs.core.types import SortDirectionType


class PaginationInput(BaseModel):
    page: int
    page_size: int
    search: str | None
    sort_direction: SortDirectionType


class BasePageInput(BaseModel):
    pagination_input: PaginationInput
    sort_by: StrEnum
