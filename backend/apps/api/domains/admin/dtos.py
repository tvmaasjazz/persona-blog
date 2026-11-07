from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from apps.api.core.dtos import (
    BasePageQueryDto,
    BasePageResponseDto,
    PaginationResponseDto,
    UsdDecimal,
)
from libs.admin.constants import MAX_CREDIT_GRANT_USD
from libs.admin.inputs import (
    AdminCreateInviteInput,
    AdminFindInvitePageInput,
    AdminFindUserCreditLedgerPageInput,
    AdminFindUserPageInput,
    AdminGrantUserCreditsInput,
    AdminSetUserActiveInput,
    AdminSetUserRoleInput,
)
from libs.admin.results import (
    AdminCreateInviteResult,
    AdminCreditLedgerEntryResult,
    AdminFindInvitePageResult,
    AdminFindUserCreditLedgerPageResult,
    AdminFindUserPageResult,
    AdminInviteDetailResult,
    AdminUserDetailResult,
)
from libs.admin.types import AdminCreditLedgerSortType, AdminInviteSortType, AdminUserSortType
from libs.credits.types import CreditLedgerEntryType
from libs.invites.constants import DEFAULT_INVITE_EXPIRES_IN_DAYS, MAX_INVITE_EXPIRES_IN_DAYS
from libs.invites.types import InviteStatusType
from libs.permissions.types import RoleType

# Above zero, at most the grant limit, and no finer than the ledger's 10 decimal places
CreditGrantAmountUsdDecimal = Annotated[
    Decimal, Field(gt=0, le=MAX_CREDIT_GRANT_USD, decimal_places=10)
]
CreditGrantNoteStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
InviteNameStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
InviteNoteStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class AdminCreditGrantDto(BaseModel):
    amount_usd: CreditGrantAmountUsdDecimal
    note: CreditGrantNoteStr

    def to_input(self) -> AdminGrantUserCreditsInput:
        return AdminGrantUserCreditsInput(amount_usd=self.amount_usd, note=self.note)


class AdminInviteDto(BaseModel):
    name: InviteNameStr
    credit_amount_usd: CreditGrantAmountUsdDecimal
    note: InviteNoteStr | None = None
    expires_in_days: Annotated[int, Field(ge=1, le=MAX_INVITE_EXPIRES_IN_DAYS)] = (
        DEFAULT_INVITE_EXPIRES_IN_DAYS
    )

    def to_input(self) -> AdminCreateInviteInput:
        # A blank note is no note
        return AdminCreateInviteInput(
            name=self.name,
            credit_amount_usd=self.credit_amount_usd,
            note=self.note or None,
            expires_in_days=self.expires_in_days,
        )


class AdminUserRoleDto(BaseModel):
    role: Literal[RoleType.READER, RoleType.CREATOR]

    def to_input(self) -> AdminSetUserRoleInput:
        return AdminSetUserRoleInput(role=self.role)


class AdminUserActiveDto(BaseModel):
    is_active: bool

    def to_input(self) -> AdminSetUserActiveInput:
        return AdminSetUserActiveInput(is_active=self.is_active)


class AdminUserPageQueryDto(BasePageQueryDto):
    sort_by: AdminUserSortType = AdminUserSortType.CREATED_AT

    def to_input(self) -> AdminFindUserPageInput:
        return AdminFindUserPageInput(
            pagination_input=self.to_pagination_input(), sort_by=self.sort_by
        )


class AdminInvitePageQueryDto(BasePageQueryDto):
    sort_by: AdminInviteSortType = AdminInviteSortType.CREATED_AT

    def to_input(self) -> AdminFindInvitePageInput:
        return AdminFindInvitePageInput(
            pagination_input=self.to_pagination_input(), sort_by=self.sort_by
        )


class AdminCreditLedgerPageQueryDto(BasePageQueryDto):
    sort_by: AdminCreditLedgerSortType = AdminCreditLedgerSortType.CREATED_AT

    def to_input(self) -> AdminFindUserCreditLedgerPageInput:
        return AdminFindUserCreditLedgerPageInput(
            pagination_input=self.to_pagination_input(), sort_by=self.sort_by
        )


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


class AdminUserPageResponseDto(BasePageResponseDto):
    users: list[AdminUserResponseDto]

    @classmethod
    def from_result(
        cls, admin_find_user_page_result: AdminFindUserPageResult
    ) -> AdminUserPageResponseDto:
        return cls(
            users=[
                AdminUserResponseDto.from_result(admin_user_detail_result)
                for admin_user_detail_result in admin_find_user_page_result.users
            ],
            pagination=PaginationResponseDto.from_result(admin_find_user_page_result.pagination),
        )


class AdminInviteCreateResponseDto(BaseModel):
    identity: UUID
    invite_url: str

    @classmethod
    def from_result(
        cls, admin_create_invite_result: AdminCreateInviteResult
    ) -> AdminInviteCreateResponseDto:
        return cls(
            identity=admin_create_invite_result.identity,
            invite_url=admin_create_invite_result.invite_url,
        )


class AdminInviteResponseDto(BaseModel):
    identity: UUID
    name: str
    credit_amount_usd: UsdDecimal
    note: str | None
    status: InviteStatusType
    expires_at: datetime
    used_at: datetime | None
    used_by_email: str | None
    revoked_at: datetime | None
    created_at: datetime
    created_by_email: str

    @classmethod
    def from_result(
        cls, admin_invite_detail_result: AdminInviteDetailResult
    ) -> AdminInviteResponseDto:
        return cls(
            identity=admin_invite_detail_result.identity,
            name=admin_invite_detail_result.name,
            credit_amount_usd=admin_invite_detail_result.credit_amount_usd,
            note=admin_invite_detail_result.note,
            status=admin_invite_detail_result.status,
            expires_at=admin_invite_detail_result.expires_at,
            used_at=admin_invite_detail_result.used_at,
            used_by_email=admin_invite_detail_result.used_by_email,
            revoked_at=admin_invite_detail_result.revoked_at,
            created_at=admin_invite_detail_result.created_at,
            created_by_email=admin_invite_detail_result.created_by_email,
        )


class AdminInvitePageResponseDto(BasePageResponseDto):
    invites: list[AdminInviteResponseDto]

    @classmethod
    def from_result(
        cls, admin_find_invite_page_result: AdminFindInvitePageResult
    ) -> AdminInvitePageResponseDto:
        return cls(
            invites=[
                AdminInviteResponseDto.from_result(admin_invite_detail_result)
                for admin_invite_detail_result in admin_find_invite_page_result.invites
            ],
            pagination=PaginationResponseDto.from_result(admin_find_invite_page_result.pagination),
        )


class AdminCreditLedgerEntryResponseDto(BaseModel):
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
    ) -> AdminCreditLedgerEntryResponseDto:
        return cls(
            identity=credit_ledger_entry_result.identity,
            entry_type=credit_ledger_entry_result.entry_type,
            amount_usd=credit_ledger_entry_result.amount_usd,
            note=credit_ledger_entry_result.note,
            generate_text_run_identity=credit_ledger_entry_result.generate_text_run_identity,
            created_by_email=credit_ledger_entry_result.created_by_email,
            created_at=credit_ledger_entry_result.created_at,
        )


class AdminCreditLedgerPageResponseDto(BasePageResponseDto):
    credit_ledger_entries: list[AdminCreditLedgerEntryResponseDto]

    @classmethod
    def from_result(
        cls, admin_find_user_credit_ledger_page_result: AdminFindUserCreditLedgerPageResult
    ) -> AdminCreditLedgerPageResponseDto:
        return cls(
            credit_ledger_entries=[
                AdminCreditLedgerEntryResponseDto.from_result(credit_ledger_entry_result)
                for credit_ledger_entry_result in (
                    admin_find_user_credit_ledger_page_result.credit_ledger_entries
                )
            ],
            pagination=PaginationResponseDto.from_result(
                admin_find_user_credit_ledger_page_result.pagination
            ),
        )
