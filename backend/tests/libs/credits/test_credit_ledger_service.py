from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.exceptions import NotFoundException
from libs.credits.results import (
    FindCreditBalanceResult,
    GrantCreditsResult,
    RefundChargesResult,
)
from libs.credits.services import CreditLedgerService
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm.credit_ledger import CreditLedgerOrm
from tests.factories.credits import (
    build_charge_credits_input,
    build_grant_credits_input,
    insert_credit_ledger_row,
)
from tests.factories.generate_text import (
    insert_generate_text_run_row,
    insert_generate_text_step_row,
)
from tests.factories.invites import insert_invite_row
from tests.factories.users import insert_user_row


async def _find_ledger_entries(
    db_session: AsyncSession, user_id: int
) -> list[tuple[Decimal, CreditLedgerEntryType, int | None, int | None]]:
    ledger_query = (
        select(
            CreditLedgerOrm.amount_usd,
            CreditLedgerOrm.entry_type,
            CreditLedgerOrm.generate_text_run_id,
            CreditLedgerOrm.generate_text_step_id,
        )
        .where(CreditLedgerOrm.user_id == user_id)
        .order_by(CreditLedgerOrm.id)
    )
    ledger_query_result = await db_session.execute(ledger_query)
    return [tuple(ledger_row) for ledger_row in ledger_query_result.all()]


async def test_charge_credits_writes_charge_row_and_lowers_balance(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    charge_credits_input = build_charge_credits_input(
        user_id=user_record.id,
        amount_usd=Decimal("0.30"),
        generate_text_run_id=run_record.id,
        generate_text_step_id=step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.charge_credits(charge_credits_input)

    await db_session.refresh(user_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == [
        (Decimal("-0.30"), CreditLedgerEntryType.CHARGE, run_record.id, step_record.id)
    ]
    assert user_record.credit_balance_usd == Decimal("4.70")


async def test_charge_credits_records_the_owner_on_the_charge_row(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    charge_credits_input = build_charge_credits_input(
        user_id=user_record.id,
        generate_text_run_id=run_record.id,
        generate_text_step_id=step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.charge_credits(charge_credits_input)

    ledger_query = select(CreditLedgerOrm).where(CreditLedgerOrm.user_id == user_record.id)
    charge_record = await db_session.scalar(ledger_query)
    assert charge_record is not None
    assert charge_record.identity is not None
    assert charge_record.created_by_id == user_record.id
    assert charge_record.note is None


async def test_charge_credits_charged_step_raises_integrity_error(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    charge_credits_input = build_charge_credits_input(
        user_id=user_record.id,
        amount_usd=Decimal("0.30"),
        generate_text_run_id=run_record.id,
        generate_text_step_id=step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)
    await credit_ledger_service.charge_credits(charge_credits_input)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await credit_ledger_service.charge_credits(charge_credits_input)

    await db_session.refresh(user_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == [
        (Decimal("-0.30"), CreditLedgerEntryType.CHARGE, run_record.id, step_record.id)
    ]
    assert user_record.credit_balance_usd == Decimal("4.70")


async def test_charge_credits_unknown_user_raises_not_found_exception_and_writes_no_row(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    charge_credits_input = build_charge_credits_input(
        user_id=999999,
        generate_text_run_id=run_record.id,
        generate_text_step_id=step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await credit_ledger_service.charge_credits(charge_credits_input)

    ledger_count_query = select(func.count(CreditLedgerOrm.id)).where(
        CreditLedgerOrm.generate_text_step_id == step_record.id
    )
    ledger_count = await db_session.scalar(ledger_count_query)
    assert ledger_count == 0


async def test_refund_charges_refunds_each_charge_and_returns_the_total(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.70"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    first_step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id, step_number=1
    )
    second_step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id, step_number=2
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.10"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=first_step_record.id,
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.20"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=second_step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    refund_charges_result = await credit_ledger_service.refund_charges(
        [first_step_record.id, second_step_record.id]
    )

    await db_session.refresh(user_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert refund_charges_result == RefundChargesResult(refund_usd=Decimal("0.30"))
    assert ledger_entries == [
        (Decimal("-0.10"), CreditLedgerEntryType.CHARGE, run_record.id, first_step_record.id),
        (Decimal("-0.20"), CreditLedgerEntryType.CHARGE, run_record.id, second_step_record.id),
        (Decimal("0.10"), CreditLedgerEntryType.REFUND, run_record.id, first_step_record.id),
        (Decimal("0.20"), CreditLedgerEntryType.REFUND, run_record.id, second_step_record.id),
    ]
    assert user_record.credit_balance_usd == Decimal("5.00")


async def test_refund_charges_called_twice_refunds_once(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.90"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.10"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)
    await credit_ledger_service.refund_charges([step_record.id])

    second_refund_charges_result = await credit_ledger_service.refund_charges([step_record.id])

    await db_session.refresh(user_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert second_refund_charges_result == RefundChargesResult(refund_usd=Decimal(0))
    assert ledger_entries == [
        (Decimal("-0.10"), CreditLedgerEntryType.CHARGE, run_record.id, step_record.id),
        (Decimal("0.10"), CreditLedgerEntryType.REFUND, run_record.id, step_record.id),
    ]
    assert user_record.credit_balance_usd == Decimal("5.00")


async def test_refund_charges_leaves_other_steps_charges_alone(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.70"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    refunded_step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id, step_number=1
    )
    kept_step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id, step_number=2
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.10"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=refunded_step_record.id,
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.20"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=kept_step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.refund_charges([refunded_step_record.id])

    await db_session.refresh(user_record)
    refund_query = select(CreditLedgerOrm.generate_text_step_id).where(
        CreditLedgerOrm.user_id == user_record.id,
        CreditLedgerOrm.entry_type == CreditLedgerEntryType.REFUND,
    )
    refund_query_result = await db_session.scalars(refund_query)
    assert list(refund_query_result.all()) == [refunded_step_record.id]
    assert user_record.credit_balance_usd == Decimal("4.80")


async def test_refund_charges_no_charges_returns_zero_and_writes_nothing(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    refund_charges_result = await credit_ledger_service.refund_charges([step_record.id])

    await db_session.refresh(user_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert refund_charges_result == RefundChargesResult(refund_usd=Decimal(0))
    assert ledger_entries == []
    assert user_record.credit_balance_usd == Decimal("5.00")


async def test_grant_credits_writes_grant_row_and_raises_balance(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("1.00"))
    admin_record = await insert_user_row(db_session)
    grant_credits_input = build_grant_credits_input(
        user_id=user_record.id, amount_usd=Decimal("5.00"), note="Welcome credit"
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.grant_credits(grant_credits_input, admin_record.id)

    await db_session.refresh(user_record)
    grant_query = select(CreditLedgerOrm).where(CreditLedgerOrm.user_id == user_record.id)
    grant_record = await db_session.scalar(grant_query)
    assert grant_record is not None
    assert grant_record.amount_usd == Decimal("5.00")
    assert grant_record.entry_type == CreditLedgerEntryType.GRANT
    assert grant_record.note == "Welcome credit"
    assert grant_record.generate_text_run_id is None
    assert grant_record.generate_text_step_id is None
    assert grant_record.created_by_id == admin_record.id
    assert grant_record.updated_by_id == admin_record.id
    assert user_record.credit_balance_usd == Decimal("6.00")


async def test_grant_credits_invite_id_is_written_to_the_ledger_row(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    admin_record = await insert_user_row(db_session)
    invite_record = await insert_invite_row(db_session, created_by_id=admin_record.id)
    grant_credits_input = build_grant_credits_input(
        user_id=user_record.id, invite_id=invite_record.id
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.grant_credits(grant_credits_input, admin_record.id)

    invite_id_query = select(CreditLedgerOrm.invite_id).where(
        CreditLedgerOrm.user_id == user_record.id
    )
    ledger_invite_id = await db_session.scalar(invite_id_query)
    assert ledger_invite_id == invite_record.id


async def test_grant_credits_without_invite_id_leaves_it_empty(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    admin_record = await insert_user_row(db_session)
    grant_credits_input = build_grant_credits_input(user_id=user_record.id)
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.grant_credits(grant_credits_input, admin_record.id)

    invite_id_query = select(CreditLedgerOrm.invite_id).where(
        CreditLedgerOrm.user_id == user_record.id
    )
    ledger_invite_id = await db_session.scalar(invite_id_query)
    assert ledger_invite_id is None


async def test_grant_credits_returns_identity_of_new_ledger_row(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    admin_record = await insert_user_row(db_session)
    grant_credits_input = build_grant_credits_input(user_id=user_record.id)
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    grant_credits_result = await credit_ledger_service.grant_credits(
        grant_credits_input, admin_record.id
    )

    grant_identity_query = select(CreditLedgerOrm.identity).where(
        CreditLedgerOrm.user_id == user_record.id
    )
    grant_identity = await db_session.scalar(grant_identity_query)
    assert grant_credits_result == GrantCreditsResult(identity=grant_identity)


async def test_grant_credits_unknown_user_raises_not_found_exception_and_writes_no_row(
    db_session: AsyncSession,
) -> None:
    admin_record = await insert_user_row(db_session)
    grant_credits_input = build_grant_credits_input(user_id=999999, note="Orphan grant")
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await credit_ledger_service.grant_credits(grant_credits_input, admin_record.id)

    orphan_grant_count_query = select(func.count(CreditLedgerOrm.id)).where(
        CreditLedgerOrm.note == "Orphan grant"
    )
    orphan_grant_count = await db_session.scalar(orphan_grant_count_query)
    assert orphan_grant_count == 0


async def test_find_credit_balance_returns_cached_balance(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("3.25"))
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    find_credit_balance_result = await credit_ledger_service.find_credit_balance(user_record.id)

    assert find_credit_balance_result == FindCreditBalanceResult(credit_balance_usd=Decimal("3.25"))


async def test_find_credit_balance_unknown_user_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await credit_ledger_service.find_credit_balance(999999)
