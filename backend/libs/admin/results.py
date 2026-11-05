from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from libs.credits.types import CreditLedgerEntryType
from libs.permissions.types import RoleType


class AdminUserDetailResult(BaseModel):
    identity: UUID
    email: str
    display_name: str | None
    role: RoleType
    credit_balance_usd: Decimal
    is_active: bool
    created_at: datetime
    last_activity_at: datetime | None


class AdminFindUserListResult(BaseModel):
    users: list[AdminUserDetailResult]


class AdminCreditLedgerEntryResult(BaseModel):
    identity: UUID
    entry_type: CreditLedgerEntryType
    amount_usd: Decimal
    note: str | None
    generate_text_run_identity: UUID | None
    created_by_email: str
    created_at: datetime


class AdminFindUserCreditLedgerResult(BaseModel):
    credit_ledger_entries: list[AdminCreditLedgerEntryResult]


class AdminGrantUserCreditsResult(BaseModel):
    identity: UUID
    user_id: int
    is_made_creator: bool


class AdminSetUserRoleResult(BaseModel):
    user_id: int
    is_changed: bool
    is_demoted_to_reader: bool


class AdminSetUserActiveResult(BaseModel):
    user_id: int
    is_changed: bool
