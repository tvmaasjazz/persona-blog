from enum import StrEnum

from pydantic import BaseModel

from libs.core.types import SortDirectionType


class PageInput(BaseModel):
    page: int
    page_size: int
    search: str | None
    sort_direction: SortDirectionType


class ListInput(BaseModel):
    page_input: PageInput
    sort_by: StrEnum
