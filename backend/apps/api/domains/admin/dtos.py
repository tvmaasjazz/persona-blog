from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from apps.api.core.dtos import UsdDecimal
from libs.admin.constants import MAX_CREDIT_GRANT_USD
from libs.admin.inputs import (
    AdminGrantUserCreditsInput,
    AdminSetUserActiveInput,
    AdminSetUserRoleInput,
)
from libs.admin.results import (
    AdminCreditLedgerEntryResult,
    AdminFindUserCreditLedgerResult,
    AdminFindUserListResult,
    AdminUserDetailResult,
)
from libs.credits.types import CreditLedgerEntryType
from libs.permissions.types import RoleType

# Above zero, at most the grant limit, and no finer than the ledger's 10 decimal places
CreditGrantAmountUsdDecimal = Annotated[
    Decimal, Field(gt=0, le=MAX_CREDIT_GRANT_USD, decimal_places=10)
]
CreditGrantNoteStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class CreditGrantDto(BaseModel):
    amount_usd: CreditGrantAmountUsdDecimal
    note: CreditGrantNoteStr

    def to_input(self) -> AdminGrantUserCreditsInput:
        return AdminGrantUserCreditsInput(amount_usd=self.amount_usd, note=self.note)


class UserRoleDto(BaseModel):
    role: Literal[RoleType.READER, RoleType.CREATOR]

    def to_input(self) -> AdminSetUserRoleInput:
        return AdminSetUserRoleInput(role=self.role)


class UserActiveDto(BaseModel):
    is_active: bool

    def to_input(self) -> AdminSetUserActiveInput:
        return AdminSetUserActiveInput(is_active=self.is_active)


class AdminUserResponseDto(BaseModel):
    identity: UUID
    email: str
    display_name: str | None
    role: RoleType
    credit_balance_usd: UsdDecimal
    is_active: bool
    created_at: datetime
    last_activity_at: datetime | None

    @classmethod
    def from_result(cls, admin_user_detail_result: AdminUserDetailResult) -> AdminUserResponseDto:
        return cls(
            identity=admin_user_detail_result.identity,
            email=admin_user_detail_result.email,
            display_name=admin_user_detail_result.display_name,
            role=admin_user_detail_result.role,
            credit_balance_usd=admin_user_detail_result.credit_balance_usd,
            is_active=admin_user_detail_result.is_active,
            created_at=admin_user_detail_result.created_at,
            last_activity_at=admin_user_detail_result.last_activity_at,
        )


class AdminUserListResponseDto(BaseModel):
    users: list[AdminUserResponseDto]

    @classmethod
    def from_result(
        cls, find_user_list_result: AdminFindUserListResult
    ) -> AdminUserListResponseDto:
        return cls(
            users=[
                AdminUserResponseDto.from_result(admin_user_detail_result)
                for admin_user_detail_result in find_user_list_result.users
            ]
        )


class CreditLedgerEntryResponseDto(BaseModel):
    identity: UUID
    entry_type: CreditLedgerEntryType
    amount_usd: UsdDecimal
    note: str | None
    generate_text_run_identity: UUID | None
    created_by_email: str
    created_at: datetime

    @classmethod
    def from_result(
        cls, credit_ledger_entry_result: AdminCreditLedgerEntryResult
    ) -> CreditLedgerEntryResponseDto:
        return cls(
            identity=credit_ledger_entry_result.identity,
            entry_type=credit_ledger_entry_result.entry_type,
            amount_usd=credit_ledger_entry_result.amount_usd,
            note=credit_ledger_entry_result.note,
            generate_text_run_identity=credit_ledger_entry_result.generate_text_run_identity,
            created_by_email=credit_ledger_entry_result.created_by_email,
            created_at=credit_ledger_entry_result.created_at,
        )


class CreditLedgerResponseDto(BaseModel):
    credit_ledger_entries: list[CreditLedgerEntryResponseDto]

    @classmethod
    def from_result(
        cls, find_user_credit_ledger_result: AdminFindUserCreditLedgerResult
    ) -> CreditLedgerResponseDto:
        return cls(
            credit_ledger_entries=[
                CreditLedgerEntryResponseDto.from_result(credit_ledger_entry_result)
                for credit_ledger_entry_result in (
                    find_user_credit_ledger_result.credit_ledger_entries
                )
            ]
        )
