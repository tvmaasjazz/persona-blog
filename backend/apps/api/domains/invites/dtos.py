from typing import Annotated

from pydantic import BaseModel, StringConstraints

from apps.api.core.dtos import UsdDecimal
from libs.invites.results import FindInviteStatusResult
from libs.invites.types import InviteStatusType

InviteCodeStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class CheckInviteDto(BaseModel):
    code: InviteCodeStr


class InviteStatusResponseDto(BaseModel):
    status: InviteStatusType
    credit_amount_usd: UsdDecimal

    @classmethod
    def from_result(
        cls, find_invite_status_result: FindInviteStatusResult
    ) -> InviteStatusResponseDto:
        return cls(
            status=find_invite_status_result.status,
            credit_amount_usd=find_invite_status_result.credit_amount_usd,
        )
