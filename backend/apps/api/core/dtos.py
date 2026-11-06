from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, StringConstraints

from libs.core.inputs import PaginationInput
from libs.core.results import PaginationResult
from libs.core.types import SortDirectionType

# A NUL byte is refused here: Postgres rejects it in text, which would be a 500
SearchStr = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=200, pattern=r"^[^\x00]*$")
]

# A USD amount in JSON, as plain digits that keep every decimal place: Pydantic's default
# str(Decimal) writes a zero rounded to 10 places as "0E-10"
UsdDecimal = Annotated[
    Decimal, PlainSerializer(lambda usd: format(usd, "f"), return_type=str, when_used="json")
]


class IdentityResponseDto(BaseModel):
    identity: UUID


class EmptyResponseDto(BaseModel):
    pass


class BasePageQueryDto(BaseModel):
    # The cap keeps (page - 1) * page_size inside Postgres's bigint OFFSET
    page: Annotated[int, Field(ge=1, le=10_000)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 20
    search: SearchStr | None = None
    sort_direction: SortDirectionType = SortDirectionType.DESC

    def to_pagination_input(self) -> PaginationInput:
        return PaginationInput(
            page=self.page,
            page_size=self.page_size,
            search=self.search or None,
            sort_direction=self.sort_direction,
        )


class PaginationResponseDto(BaseModel):
    page: int
    page_size: int
    total: int

    @classmethod
    def from_result(cls, pagination_result: PaginationResult) -> PaginationResponseDto:
        return cls(
            page=pagination_result.page,
            page_size=pagination_result.page_size,
            total=pagination_result.total,
        )


class BasePageResponseDto(BaseModel):
    pagination: PaginationResponseDto
