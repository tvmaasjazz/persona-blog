from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, StringConstraints

from libs.core.inputs import PageInput
from libs.core.results import PageInfoResult
from libs.core.types import SortDirectionType

SearchStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]

# A USD amount in JSON, as plain digits that keep every decimal place: Pydantic's default
# str(Decimal) writes a zero rounded to 10 places as "0E-10"
UsdDecimal = Annotated[
    Decimal, PlainSerializer(lambda usd: format(usd, "f"), return_type=str, when_used="json")
]


class IdentityResponseDto(BaseModel):
    identity: UUID


class EmptyResponseDto(BaseModel):
    pass


class PageQueryDto(BaseModel):
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 20
    search: SearchStr | None = None
    sort_direction: SortDirectionType = SortDirectionType.DESC

    def to_page_input(self) -> PageInput:
        return PageInput(
            page=self.page,
            page_size=self.page_size,
            search=self.search or None,
            sort_direction=self.sort_direction,
        )


class PageInfoResponseDto(BaseModel):
    page: int
    page_size: int
    total: int

    @classmethod
    def from_result(cls, page_info_result: PageInfoResult) -> PageInfoResponseDto:
        return cls(
            page=page_info_result.page,
            page_size=page_info_result.page_size,
            total=page_info_result.total,
        )


class PageResponseDto(BaseModel):
    page_info: PageInfoResponseDto
