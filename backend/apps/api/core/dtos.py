from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, PlainSerializer

# A USD amount in JSON, as plain digits that keep every decimal place: Pydantic's default
# str(Decimal) writes a zero rounded to 10 places as "0E-10"
UsdDecimal = Annotated[
    Decimal, PlainSerializer(lambda usd: format(usd, "f"), return_type=str, when_used="json")
]


class IdentityResponseDto(BaseModel):
    identity: UUID


class EmptyResponseDto(BaseModel):
    pass
