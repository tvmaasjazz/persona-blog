from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.exceptions import AdminCreditGrantSystemUserException
from libs.admin.inputs import GrantUserCreditsInput
from libs.admin.results import (
    CreditLedgerEntryResult,
    FindUserCreditLedgerResult,
    GrantUserCreditsResult,
)
from libs.admin.services import AdminCreditService
from libs.core.exceptions import NotFoundException
from libs.credits.services import CreditLedgerService
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm import CreditLedgerOrm, RoleOrm, UserOrm
from libs.permissions.types import RoleType
from tests.factories.auth import build_auth_user
from tests.factories.credits import insert_credit_ledger_row
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.users import find_system_user_row, insert_user_row


def _build_admin_credit_service(db_session: AsyncSession) -> AdminCreditService:
    return AdminCreditService(
        db_session=db_session,
        credit_ledger_service=CreditLedgerService(db_session=db_session),
    )


async def _count_ledger_rows(db_session: AsyncSession) -> int | None:
    ledger_count_query = select(func.count(CreditLedgerOrm.id))
    return await db_session.scalar(ledger_count_query)


async def test_find_user_credit_ledger_returns_rows_newest_first_with_run_and_creator(
    db_session: AsyncSession,
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
    admin_credit_service = _build_admin_credit_service(db_session)

    find_user_credit_ledger_result = await admin_credit_service.find_user_credit_ledger(
        user_record.identity
    )

    assert find_user_credit_ledger_result == FindUserCreditLedgerResult(
        credit_ledger_entries=[
            CreditLedgerEntryResult(
                identity=newer_charge_record.identity,
                entry_type=CreditLedgerEntryType.CHARGE,
                amount_usd=Decimal("-0.30"),
                note=None,
                generate_text_run_identity=run_record.identity,
                created_by_email="ada@example.com",
                created_at=newer_created_at,
            ),
            CreditLedgerEntryResult(
                identity=older_grant_record.identity,
                entry_type=CreditLedgerEntryType.GRANT,
                amount_usd=Decimal("5.00"),
                note="Welcome credit",
                generate_text_run_identity=None,
                created_by_email="admin@example.com",
                created_at=older_created_at,
            ),
        ]
    )


async def test_find_user_credit_ledger_same_created_at_orders_by_id_descending(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    first_ledger_record = await insert_credit_ledger_row(db_session, user_id=user_record.id)
    second_ledger_record = await insert_credit_ledger_row(db_session, user_id=user_record.id)
    admin_credit_service = _build_admin_credit_service(db_session)

    find_user_credit_ledger_result = await admin_credit_service.find_user_credit_ledger(
        user_record.identity
    )

    listed_identities = [
        credit_ledger_entry.identity
        for credit_ledger_entry in find_user_credit_ledger_result.credit_ledger_entries
    ]
    assert listed_identities == [second_ledger_record.identity, first_ledger_record.identity]


async def test_find_user_credit_ledger_user_without_rows_returns_empty_list(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    admin_credit_service = _build_admin_credit_service(db_session)

    find_user_credit_ledger_result = await admin_credit_service.find_user_credit_ledger(
        user_record.identity
    )

    assert find_user_credit_ledger_result == FindUserCreditLedgerResult(credit_ledger_entries=[])


async def test_find_user_credit_ledger_unknown_identity_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    admin_credit_service = _build_admin_credit_service(db_session)

    with pytest.raises(NotFoundException):
        await admin_credit_service.find_user_credit_ledger(uuid4())


async def test_find_user_credit_ledger_system_user_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    system_user_record = await find_system_user_row(db_session)
    admin_credit_service = _build_admin_credit_service(db_session)

    with pytest.raises(NotFoundException):
        await admin_credit_service.find_user_credit_ledger(system_user_record.identity)


async def test_grant_user_credits_writes_grant_row_and_raises_balance(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(
        db_session, role=RoleType.CREATOR, credit_balance_usd=Decimal("1.00")
    )
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = GrantUserCreditsInput(
        amount_usd=Decimal("5.00"), note="Welcome credit"
    )
    admin_credit_service = _build_admin_credit_service(db_session)

    grant_user_credits_result = await admin_credit_service.grant_user_credits(
        user_record.identity, grant_user_credits_input, admin_auth_user
    )

    await db_session.refresh(user_record)
    grant_query = select(CreditLedgerOrm).where(CreditLedgerOrm.user_id == user_record.id)
    grant_record = await db_session.scalar(grant_query)
    assert grant_record is not None
    assert grant_user_credits_result == GrantUserCreditsResult(
        identity=grant_record.identity, user_id=user_record.id, is_made_creator=False
    )
    assert grant_record.amount_usd == Decimal("5.00")
    assert grant_record.entry_type == CreditLedgerEntryType.GRANT
    assert grant_record.note == "Welcome credit"
    assert grant_record.created_by_id == admin_record.id
    assert user_record.credit_balance_usd == Decimal("6.00")


async def test_grant_user_credits_reader_becomes_creator(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = GrantUserCreditsInput(amount_usd=Decimal("5.00"), note="Welcome")
    admin_credit_service = _build_admin_credit_service(db_session)

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
    db_session: AsyncSession, role: RoleType
) -> None:
    user_record = await insert_user_row(db_session, role=role)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = GrantUserCreditsInput(amount_usd=Decimal("5.00"), note="Top up")
    admin_credit_service = _build_admin_credit_service(db_session)

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


async def test_grant_user_credits_inactive_user_is_granted(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(
        db_session, is_active=False, credit_balance_usd=Decimal("0.00")
    )
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = GrantUserCreditsInput(amount_usd=Decimal("2.00"), note="Reinstated")
    admin_credit_service = _build_admin_credit_service(db_session)

    await admin_credit_service.grant_user_credits(
        user_record.identity, grant_user_credits_input, admin_auth_user
    )

    await db_session.refresh(user_record)
    assert user_record.credit_balance_usd == Decimal("2.00")


async def test_grant_user_credits_unknown_identity_raises_not_found_and_writes_nothing(
    db_session: AsyncSession,
) -> None:
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = GrantUserCreditsInput(amount_usd=Decimal("5.00"), note="Orphan")
    admin_credit_service = _build_admin_credit_service(db_session)

    with pytest.raises(NotFoundException):
        await admin_credit_service.grant_user_credits(
            uuid4(), grant_user_credits_input, admin_auth_user
        )

    ledger_row_count = await _count_ledger_rows(db_session)
    assert ledger_row_count == 0


async def test_grant_user_credits_system_user_raises_admin_credit_grant_system_user_exception(
    db_session: AsyncSession,
) -> None:
    system_user_record = await find_system_user_row(db_session)
    admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
    admin_auth_user = build_auth_user(
        user_id=admin_record.id, user_identity=admin_record.identity, role=RoleType.ADMIN
    )
    grant_user_credits_input = GrantUserCreditsInput(amount_usd=Decimal("5.00"), note="Nope")
    admin_credit_service = _build_admin_credit_service(db_session)

    with pytest.raises(AdminCreditGrantSystemUserException):
        await admin_credit_service.grant_user_credits(
            system_user_record.identity, grant_user_credits_input, admin_auth_user
        )

    ledger_row_count = await _count_ledger_rows(db_session)
    assert ledger_row_count == 0
