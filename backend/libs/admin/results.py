from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from libs.core.results import PaginationResult
from libs.credits.types import CreditLedgerEntryType
from libs.invites.types import InviteStatusType
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


class AdminFindUserPageResult(BaseModel):
    users: list[AdminUserDetailResult]
    pagination: PaginationResult


class AdminCreditLedgerEntryResult(BaseModel):
    identity: UUID
    entry_type: CreditLedgerEntryType
    amount_usd: Decimal
    note: str | None
    generate_text_run_identity: UUID | None
    created_by_email: str
    created_at: datetime


class AdminFindUserCreditLedgerPageResult(BaseModel):
    credit_ledger_entries: list[AdminCreditLedgerEntryResult]
    pagination: PaginationResult


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


class AdminCreateInviteResult(BaseModel):
    identity: UUID
    invite_url: str


class AdminInviteDetailResult(BaseModel):
    identity: UUID
    name: str
    credit_amount_usd: Decimal
    note: str | None
    status: InviteStatusType
    expires_at: datetime
    used_at: datetime | None
    used_by_email: str | None
    revoked_at: datetime | None
    created_at: datetime
    created_by_email: str


class AdminFindInvitePageResult(BaseModel):
    invites: list[AdminInviteDetailResult]
    pagination: PaginationResult
