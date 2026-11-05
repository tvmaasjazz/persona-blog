from decimal import Decimal

from pydantic import BaseModel

from libs.permissions.types import RoleType


class AdminGrantUserCreditsInput(BaseModel):
    amount_usd: Decimal
    note: str


class AdminSetUserRoleInput(BaseModel):
    role: RoleType


class AdminSetUserActiveInput(BaseModel):
    is_active: bool


class AdminCreateInviteInput(BaseModel):
    name: str
    credit_amount_usd: Decimal
    note: str | None
    expires_in_days: int
