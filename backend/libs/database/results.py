from typing import Any

from pydantic import BaseModel

from libs.core.results import PaginationResult


class FindPageResult(BaseModel):
    records: list[Any]
    pagination: PaginationResult
