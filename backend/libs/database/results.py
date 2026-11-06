from typing import Any

from pydantic import BaseModel

from libs.core.results import PageInfoResult


class FindPageResult(BaseModel):
    records: list[Any]
    page_info: PageInfoResult
