from decimal import Decimal

from pydantic import BaseModel

from libs.invites.types import InviteSignInResultType, InviteStatusType


class FindInviteStatusResult(BaseModel):
    status: InviteStatusType
    credit_amount_usd: Decimal


class RedeemInviteResult(BaseModel):
    result_type: InviteSignInResultType
    is_made_creator: bool
