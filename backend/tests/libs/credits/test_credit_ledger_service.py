from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.exceptions import NotFoundException
from libs.credits.results import FindCreditBalanceResult
from libs.credits.services import CreditLedgerService
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm.credit_ledger import CreditLedgerOrm
from libs.generate_text.types import GenerateTextStepStatusType
from tests.factories.auth import build_auth_user
from tests.factories.credits import build_grant_credits_input, insert_credit_ledger_row
from tests.factories.generate_text import (
    insert_generate_text_run_row,
    insert_generate_text_step_row,
)
from tests.factories.users import insert_user_row

DECIDED_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


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


async def test_charge_generate_text_step_writes_charge_row_and_lowers_balance_and_raises_run_charge(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, charge_usd=Decimal("0.10")
    )
    step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        charge_usd=Decimal("0.30"),
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.charge_generate_text_step(step_record.id)

    await db_session.refresh(user_record)
    await db_session.refresh(run_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == [
        (Decimal("-0.30"), CreditLedgerEntryType.CHARGE, run_record.id, step_record.id)
    ]
    assert user_record.credit_balance_usd == Decimal("4.70")
    assert run_record.charge_usd == Decimal("0.40")


async def test_charge_generate_text_step_records_the_owner_on_the_charge_row(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        charge_usd=Decimal("0.30"),
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.charge_generate_text_step(step_record.id)

    ledger_query = select(CreditLedgerOrm).where(CreditLedgerOrm.user_id == user_record.id)
    charge_record = await db_session.scalar(ledger_query)
    assert charge_record is not None
    assert charge_record.identity is not None
    assert charge_record.created_by_id == user_record.id
    assert charge_record.note is None


async def test_charge_generate_text_step_zero_charge_writes_nothing(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        charge_usd=Decimal("0"),
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.charge_generate_text_step(step_record.id)

    await db_session.refresh(user_record)
    await db_session.refresh(run_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == []
    assert user_record.credit_balance_usd == Decimal("5.00")
    assert run_record.charge_usd == Decimal("0")


async def test_charge_generate_text_step_unknown_step_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await credit_ledger_service.charge_generate_text_step(999999)


async def test_refund_failed_generate_text_run_segment_no_review_step_refunds_every_charge(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.70"))
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, charge_usd=Decimal("0.30")
    )
    first_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        step_number=1,
        status=GenerateTextStepStatusType.SUCCEEDED,
        charge_usd=Decimal("0.10"),
    )
    second_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        step_number=2,
        status=GenerateTextStepStatusType.SUCCEEDED,
        charge_usd=Decimal("0.20"),
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

    await credit_ledger_service.refund_failed_generate_text_run_segment(run_record.id)

    await db_session.refresh(user_record)
    await db_session.refresh(run_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == [
        (Decimal("-0.10"), CreditLedgerEntryType.CHARGE, run_record.id, first_step_record.id),
        (Decimal("-0.20"), CreditLedgerEntryType.CHARGE, run_record.id, second_step_record.id),
        (Decimal("0.10"), CreditLedgerEntryType.REFUND, run_record.id, first_step_record.id),
        (Decimal("0.20"), CreditLedgerEntryType.REFUND, run_record.id, second_step_record.id),
    ]
    assert user_record.credit_balance_usd == Decimal("5.00")
    assert run_record.charge_usd == Decimal("0")


async def test_refund_failed_generate_text_run_segment_keeps_charges_before_a_decided_step(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.70"))
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, charge_usd=Decimal("0.30")
    )
    outline_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        step_number=1,
        step_name="GENERATE_OUTLINE",
        status=GenerateTextStepStatusType.SUCCEEDED,
        charge_usd=Decimal("0.10"),
        decided_at=DECIDED_AT,
    )
    draft_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        step_number=2,
        step_name="GENERATE_DRAFT",
        status=GenerateTextStepStatusType.SUCCEEDED,
        charge_usd=Decimal("0.20"),
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.10"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=outline_step_record.id,
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.20"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=draft_step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.refund_failed_generate_text_run_segment(run_record.id)

    await db_session.refresh(user_record)
    await db_session.refresh(run_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == [
        (Decimal("-0.10"), CreditLedgerEntryType.CHARGE, run_record.id, outline_step_record.id),
        (Decimal("-0.20"), CreditLedgerEntryType.CHARGE, run_record.id, draft_step_record.id),
        (Decimal("0.20"), CreditLedgerEntryType.REFUND, run_record.id, draft_step_record.id),
    ]
    assert user_record.credit_balance_usd == Decimal("4.90")
    assert run_record.charge_usd == Decimal("0.10")


async def test_refund_failed_generate_text_run_segment_undecided_review_step_keeps_its_charge(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.90"))
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, charge_usd=Decimal("0.10")
    )
    outline_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        step_number=1,
        step_name="GENERATE_OUTLINE",
        status=GenerateTextStepStatusType.AWAITING_REVIEW,
        charge_usd=Decimal("0.10"),
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.10"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=outline_step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.refund_failed_generate_text_run_segment(run_record.id)

    await db_session.refresh(user_record)
    await db_session.refresh(run_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == [
        (Decimal("-0.10"), CreditLedgerEntryType.CHARGE, run_record.id, outline_step_record.id)
    ]
    assert user_record.credit_balance_usd == Decimal("4.90")
    assert run_record.charge_usd == Decimal("0.10")


async def test_refund_failed_generate_text_run_segment_undecided_review_step_refunds_later_steps(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.70"))
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, charge_usd=Decimal("0.30")
    )
    outline_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        step_number=1,
        status=GenerateTextStepStatusType.AWAITING_REVIEW,
        charge_usd=Decimal("0.10"),
    )
    draft_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        step_number=2,
        status=GenerateTextStepStatusType.SUCCEEDED,
        charge_usd=Decimal("0.20"),
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.10"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=outline_step_record.id,
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.20"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=run_record.id,
        generate_text_step_id=draft_step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.refund_failed_generate_text_run_segment(run_record.id)

    await db_session.refresh(user_record)
    await db_session.refresh(run_record)
    refund_query = select(CreditLedgerOrm.generate_text_step_id).where(
        CreditLedgerOrm.user_id == user_record.id,
        CreditLedgerOrm.entry_type == CreditLedgerEntryType.REFUND,
    )
    refunded_step_ids = (await db_session.scalars(refund_query)).all()
    assert list(refunded_step_ids) == [draft_step_record.id]
    assert user_record.credit_balance_usd == Decimal("4.90")
    assert run_record.charge_usd == Decimal("0.10")


async def test_refund_failed_generate_text_run_segment_leaves_another_runs_charges_alone(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("4.50"))
    failed_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, charge_usd=Decimal("0.20")
    )
    other_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, charge_usd=Decimal("0.30")
    )
    failed_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=failed_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        charge_usd=Decimal("0.20"),
    )
    other_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=other_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        charge_usd=Decimal("0.30"),
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.20"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=failed_run_record.id,
        generate_text_step_id=failed_step_record.id,
    )
    await insert_credit_ledger_row(
        db_session,
        user_id=user_record.id,
        amount_usd=Decimal("-0.30"),
        entry_type=CreditLedgerEntryType.CHARGE,
        generate_text_run_id=other_run_record.id,
        generate_text_step_id=other_step_record.id,
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.refund_failed_generate_text_run_segment(failed_run_record.id)

    await db_session.refresh(user_record)
    await db_session.refresh(other_run_record)
    assert user_record.credit_balance_usd == Decimal("4.70")
    assert other_run_record.charge_usd == Decimal("0.30")


async def test_refund_failed_generate_text_run_segment_no_charges_writes_nothing(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("5.00"))
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.refund_failed_generate_text_run_segment(run_record.id)

    await db_session.refresh(user_record)
    ledger_entries = await _find_ledger_entries(db_session, user_record.id)
    assert ledger_entries == []
    assert user_record.credit_balance_usd == Decimal("5.00")


async def test_grant_credits_writes_grant_row_and_raises_balance(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("1.00"))
    admin_record = await insert_user_row(db_session)
    admin_auth_user = build_auth_user(user_id=admin_record.id, user_identity=admin_record.identity)
    grant_credits_input = build_grant_credits_input(
        user_id=user_record.id, amount_usd=Decimal("5.00"), note="Welcome credit"
    )
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    await credit_ledger_service.grant_credits(grant_credits_input, admin_auth_user)

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


async def test_grant_credits_unknown_user_raises_not_found_exception_and_writes_no_row(
    db_session: AsyncSession,
) -> None:
    admin_record = await insert_user_row(db_session)
    admin_auth_user = build_auth_user(user_id=admin_record.id, user_identity=admin_record.identity)
    grant_credits_input = build_grant_credits_input(user_id=999999, note="Orphan grant")
    credit_ledger_service = CreditLedgerService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await credit_ledger_service.grant_credits(grant_credits_input, admin_auth_user)

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
