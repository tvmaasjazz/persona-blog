from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.exceptions import AdminCreditGrantSystemUserException
from libs.admin.inputs import AdminGrantUserCreditsInput
from libs.admin.results import (
    AdminCreditLedgerEntryResult,
    AdminFindUserCreditLedgerPageResult,
    AdminGrantUserCreditsResult,
)
from libs.admin.services import AdminCreditService
from libs.admin.types import AdminCreditLedgerSortType
from libs.core.exceptions import NotFoundException
from libs.core.results import PaginationResult
from libs.core.types import SortDirectionType
from libs.credits.services import CreditLedgerService
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm import CreditLedgerOrm, RoleOrm, UserOrm
from libs.database.services import PaginationService
from libs.permissions.types import RoleType
from libs.users.services import UserService
from tests.factories.admin import build_admin_find_user_credit_ledger_page_input
from tests.factories.auth import build_auth_user
from tests.factories.credits import insert_credit_ledger_row
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.users import find_system_user_row, insert_user_row


@pytest.fixture
def admin_credit_service(
    db_session: AsyncSession, pagination_service: PaginationService
) -> AdminCreditService:
    return AdminCreditService(
        db_session=db_session,
        credit_ledger_service=CreditLedgerService(db_session=db_session),
        user_service=UserService(
            db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
        ),
        pagination_service=pagination_service,
    )


async def _count_ledger_rows(db_session: AsyncSession) -> int | None:
    ledger_count_query = select(func.count(CreditLedgerOrm.id))
    return await db_session.scalar(ledger_count_query)


def _find_ledger_notes(
    admin_find_user_credit_ledger_page_result: AdminFindUserCreditLedgerPageResult,
) -> list[str | None]:
    return [
        credit_ledger_entry.note
        for credit_ledger_entry in admin_find_user_credit_ledger_page_result.credit_ledger_entries
    ]


async def test_find_user_credit_ledger_page_returns_rows_newest_first_with_run_and_creator(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com")
    admin_record = await insert_user_row(db_session, email="admin@example.com")
    other_user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    older_created_at = datetime(2026, 1, 1, tzinfo=UTC)
    newer_created_at = datetime(2026, 2, 1, tzinfo=UTC)
    older_grant_record = await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("5.00"),
        note="Welcome credit",
        created_by_id=admin_record.id,
        created_at=older_created_at,
    )
    newer_charge_record = await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.30"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        created_at=newer_created_at,
    )
    await insert_credit_ledger_row(db_session, user_id=other_user_record.id)

    admin_find_user_credit_ledger_page_result = (
        await admin_credit_service.find_user_credit_ledger_page(
            user_record.identity, build_admin_find_user_credit_ledger_page_input(page_size=10)
        )
    )

    assert admin_find_user_credit_ledger_page_result == AdminFindUserCreditLedgerPageResult(
        credit_ledger_entries=[
            AdminCreditLedgerEntryResult(
                identity=newer_charge_record.identity,
                entry_type=CreditLedgerEntryType.CHARGE,
                amount_usd=Decimal("-0.30"),
                note=None,
                generate_text_run_identity=run_record.identity,
                created_by_email="ada@example.com",
                created_at=newer_created_at,
            ),
            AdminCreditLedgerEntryResult(
                identity=older_grant_record.identity,
                entry_type=CreditLedgerEntryType.GRANT,
                amount_usd=Decimal("5.00"),
                note="Welcome credit",
                generate_text_run_identity=None,
                created_by_email="admin@example.com",
                created_at=older_created_at,
            ),
        ],
        pagination=PaginationResult(page=1, page_size=10, total=2),
    )


async def test_find_user_credit_ledger_page_same_created_at_orders_by_id_descending(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(db_session)
    first_ledger_record = await insert_credit_ledger_row(db_session, user_id=user_record.id)
    second_ledger_record = await insert_credit_ledger_row(db_session, user_id=user_record.id)

    admin_find_user_credit_ledger_page_result = (
        await admin_credit_service.find_user_credit_ledger_page(
            user_record.identity, build_admin_find_user_credit_ledger_page_input()
        )
    )

    listed_identities = [
        credit_ledger_entry.identity
        for credit_ledger_entry in admin_find_user_credit_ledger_page_result.credit_ledger_entries
    ]
    assert listed_identities == [second_ledger_record.identity, first_ledger_record.identity]


async def test_find_user_credit_ledger_page_user_without_rows_returns_empty_page(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(db_session)

    admin_find_user_credit_ledger_page_result = (
        await admin_credit_service.find_user_credit_ledger_page(
            user_record.identity, build_admin_find_user_credit_ledger_page_input()
        )
    )

    assert admin_find_user_credit_ledger_page_result == AdminFindUserCreditLedgerPageResult(
        credit_ledger_entries=[], pagination=PaginationResult(page=1, page_size=20, total=0)
    )


async def test_find_user_credit_ledger_page_unknown_identity_raises_not_found_exception(
    admin_credit_service: AdminCreditService,
) -> None:
    with pytest.raises(NotFoundException):
        await admin_credit_service.find_user_credit_ledger_page(
            uuid4(), build_admin_find_user_credit_ledger_page_input()
        )


async def test_find_user_credit_ledger_page_system_user_raises_not_found_exception(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    system_user_record = await find_system_user_row(db_session)

    with pytest.raises(NotFoundException):
        await admin_credit_service.find_user_credit_ledger_page(
            system_user_record.identity, build_admin_find_user_credit_ledger_page_input()
        )


async def test_find_user_credit_ledger_page_total_counts_only_the_users_rows_and_pages_slice_them(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    for day, note in enumerate(["Entry 1", "Entry 2", "Entry 3", "Entry 4", "Entry 5"], 1):
        await insert_credit_ledger_row(
            db_session,
            user_id=user_record.id,
            note=note,
            created_at=datetime(2026, 1, day, tzinfo=UTC),
        )
    await insert_credit_ledger_row(db_session, user_id=other_user_record.id, note="Other user")

    admin_find_user_credit_ledger_page_result = (
        await admin_credit_service.find_user_credit_ledger_page(
            user_record.identity,
            build_admin_find_user_credit_ledger_page_input(page=2, page_size=2),
        )
    )

    assert _find_ledger_notes(admin_find_user_credit_ledger_page_result) == ["Entry 3", "Entry 2"]
    assert admin_find_user_credit_ledger_page_result.pagination == PaginationResult(
        page=2, page_size=2, total=5
    )


async def test_find_user_credit_ledger_page_page_past_the_end_returns_no_rows_and_same_total(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(db_session)
    for _ in range(3):
        await insert_credit_ledger_row(db_session, user_id=user_record.id)

    admin_find_user_credit_ledger_page_result = (
        await admin_credit_service.find_user_credit_ledger_page(
            user_record.identity,
            build_admin_find_user_credit_ledger_page_input(page=3, page_size=2),
        )
    )

    assert admin_find_user_credit_ledger_page_result == AdminFindUserCreditLedgerPageResult(
        credit_ledger_entries=[], pagination=PaginationResult(page=3, page_size=2, total=3)
    )


@pytest.mark.parametrize(
    ("sort_direction", "expected_notes"),
    [
        pytest.param(SortDirectionType.ASC, ["Oldest", "Middle", "Newest"], id="ascending"),
        pytest.param(SortDirectionType.DESC, ["Newest", "Middle", "Oldest"], id="descending"),
    ],
)
async def test_find_user_credit_ledger_page_sorted_by_created_at(
    db_session: AsyncSession,
    admin_credit_service: AdminCreditService,
    sort_direction: SortDirectionType,
    expected_notes: list[str],
) -> None:
    user_record = await insert_user_row(db_session)
    for note, created_at in [
        ("Middle", datetime(2026, 1, 2, tzinfo=UTC)),
        ("Newest", datetime(2026, 1, 3, tzinfo=UTC)),
        ("Oldest", datetime(2026, 1, 1, tzinfo=UTC)),
    ]:
        await insert_credit_ledger_row(
            db_session, user_id=user_record.id, note=note, created_at=created_at
        )

    admin_find_user_credit_ledger_page_result = (
        await admin_credit_service.find_user_credit_ledger_page(
            user_record.identity,
            build_admin_find_user_credit_ledger_page_input(
                sort_by=AdminCreditLedgerSortType.CREATED_AT, sort_direction=sort_direction
            ),
        )
    )

    assert _find_ledger_notes(admin_find_user_credit_ledger_page_result) == expected_notes


@pytest.mark.parametrize(
    ("search", "expected_notes"),
    [
        pytest.param("welcome", ["Welcome credit"], id="note"),
        pytest.param("TOP UP", ["Top up"], id="ignores_case"),
        pytest.param("null", [], id="null_note_does_not_match"),
        pytest.param("none", [], id="null_note_does_not_match_none_text"),
        pytest.param("ada@example.com", [], id="creator_email_is_not_searched"),
        pytest.param("%", [], id="percent_is_literal"),
        pytest.param("   ", ["Welcome credit", "Top up", None], id="whitespace_is_no_search"),
    ],
)
async def test_find_user_credit_ledger_page_search(
    db_session: AsyncSession,
    admin_credit_service: AdminCreditService,
    search: str,
    expected_notes: list[str | None],
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com")
    for note, created_at in [
        ("Welcome credit", datetime(2026, 1, 1, tzinfo=UTC)),
        ("Top up", datetime(2026, 1, 2, tzinfo=UTC)),
        (None, datetime(2026, 1, 3, tzinfo=UTC)),
    ]:
        await insert_credit_ledger_row(
            db_session, user_id=user_record.id, note=note, created_at=created_at
        )

    admin_find_user_credit_ledger_page_result = (
        await admin_credit_service.find_user_credit_ledger_page(
            user_record.identity,
            build_admin_find_user_credit_ledger_page_input(
                search=search, sort_direction=SortDirectionType.ASC
            ),
        )
    )

    assert _find_ledger_notes(admin_find_user_credit_ledger_page_result) == expected_notes


async def test_grant_user_credits_writes_grant_row_and_raises_balance(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(
        db_session, role=RoleType.CREATOR, credit_balance_usd=Decimal("1.00")
    )
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = AdminGrantUserCreditsInput(
        amount_usd=Decimal("5.00"), note="Welcome credit"
    )

    grant_user_credits_result = await admin_credit_service.grant_user_credits(
        user_record.identity, grant_user_credits_input, admin_auth_user
    )

    await db_session.refresh(user_record)
    grant_query = select(CreditLedgerOrm).where(CreditLedgerOrm.user_id == user_record.id)
    grant_record = await db_session.scalar(grant_query)
    assert grant_record is not None
    assert grant_user_credits_result == AdminGrantUserCreditsResult(
        identity=grant_record.identity, user_id=user_record.id, is_made_creator=False
    )
    assert grant_record.amount_usd == Decimal("5.00")
    assert grant_record.entry_type == CreditLedgerEntryType.GRANT
    assert grant_record.note == "Welcome credit"
    assert grant_record.created_by_id == admin_record.id
    assert user_record.credit_balance_usd == Decimal("6.00")


async def test_grant_user_credits_reader_becomes_creator(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = AdminGrantUserCreditsInput(
        amount_usd=Decimal("5.00"), note="Welcome"
    )

    grant_user_credits_result = await admin_credit_service.grant_user_credits(
        user_record.identity, grant_user_credits_input, admin_auth_user
    )

    role_code_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == user_record.id)
    )
    updated_by_id_query = select(UserOrm.updated_by_id).where(UserOrm.id == user_record.id)
    role_code = await db_session.scalar(role_code_query)
    updated_by_id = await db_session.scalar(updated_by_id_query)
    assert grant_user_credits_result.is_made_creator is True
    assert role_code == RoleType.CREATOR
    assert updated_by_id == admin_record.id


@pytest.mark.parametrize("role", [RoleType.CREATOR, RoleType.ADMIN])
async def test_grant_user_credits_creator_or_admin_keeps_role(
    db_session: AsyncSession, role: RoleType, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(db_session, role=role)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = AdminGrantUserCreditsInput(amount_usd=Decimal("5.00"), note="Top up")

    grant_user_credits_result = await admin_credit_service.grant_user_credits(
        user_record.identity, grant_user_credits_input, admin_auth_user
    )

    role_code_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == user_record.id)
    )
    role_code = await db_session.scalar(role_code_query)
    assert grant_user_credits_result.is_made_creator is False
    assert role_code == role


async def test_grant_user_credits_inactive_user_is_granted(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    user_record = await insert_user_row(
        db_session, is_active=False, credit_balance_usd=Decimal("0.00")
    )
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = AdminGrantUserCreditsInput(
        amount_usd=Decimal("2.00"), note="Reinstated"
    )

    await admin_credit_service.grant_user_credits(
        user_record.identity, grant_user_credits_input, admin_auth_user
    )

    await db_session.refresh(user_record)
    assert user_record.credit_balance_usd == Decimal("2.00")


async def test_grant_user_credits_unknown_identity_raises_not_found_and_writes_nothing(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = AdminGrantUserCreditsInput(amount_usd=Decimal("5.00"), note="Orphan")

    with pytest.raises(NotFoundException):
        await admin_credit_service.grant_user_credits(
            uuid4(), grant_user_credits_input, admin_auth_user
        )

    ledger_row_count = await _count_ledger_rows(db_session)
    assert ledger_row_count == 0


async def test_grant_user_credits_system_user_raises_admin_credit_grant_system_user_exception(
    db_session: AsyncSession, admin_credit_service: AdminCreditService
) -> None:
    system_user_record = await find_system_user_row(db_session)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = AdminGrantUserCreditsInput(amount_usd=Decimal("5.00"), note="Nope")

    with pytest.raises(AdminCreditGrantSystemUserException):
        await admin_credit_service.grant_user_credits(
            system_user_record.identity, grant_user_credits_input, admin_auth_user
        )

    ledger_row_count = await _count_ledger_rows(db_session)
    assert ledger_row_count == 0
