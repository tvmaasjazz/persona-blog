from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from libs.credits.inputs import ChargeCreditsInput, GrantCreditsInput
from libs.credits.settings import CreditSettings
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm.credit_ledger import CreditLedgerOrm


def build_credit_settings(
    *,
    markup_multiplier: Decimal = Decimal("1"),
    minimum_run_balance_usd: Decimal = Decimal("0.10"),
    low_balance_threshold_usd: Decimal = Decimal("0.50"),
) -> CreditSettings:
    return CreditSettings(
        markup_multiplier=markup_multiplier,
        minimum_run_balance_usd=minimum_run_balance_usd,
        low_balance_threshold_usd=low_balance_threshold_usd,
    )


def build_charge_credits_input(
    *,
    user_id: int,
    generate_text_run_id: int,
    generate_text_step_id: int,
    amount_usd: Decimal = Decimal("0.10"),
) -> ChargeCreditsInput:
    return ChargeCreditsInput(
        user_id=user_id,
        amount_usd=amount_usd,
        generate_text_run_id=generate_text_run_id,
        generate_text_step_id=generate_text_step_id,
    )


def build_grant_credits_input(
    *, user_id: int, amount_usd: Decimal = Decimal("5.00"), note: str | None = None
) -> GrantCreditsInput:
    return GrantCreditsInput(user_id=user_id, amount_usd=amount_usd, note=note)


async def insert_credit_ledger_row(
    db_session: AsyncSession,
    *,
    user_id: int,
    amount_usd: Decimal = Decimal("1.00"),
    entry_type: CreditLedgerEntryType = CreditLedgerEntryType.GRANT,
    generate_text_run_id: int | None = None,
    generate_text_step_id: int | None = None,
    note: str | None = None,
    created_by_id: int | None = None,
    created_at: datetime | None = None,
) -> CreditLedgerOrm:
    # The row's own user wrote it unless the test names someone else, such as an admin
    author_id = user_id if created_by_id is None else created_by_id
    credit_ledger_record = CreditLedgerOrm(
        user_id=user_id,
        amount_usd=amount_usd,
        entry_type=entry_type,
        generate_text_run_id=generate_text_run_id,
        generate_text_step_id=generate_text_step_id,
        note=note,
        created_by_id=author_id,
        updated_by_id=author_id,
    )
    # Left unset, the column's default fills it in
    if created_at is not None:
        credit_ledger_record.created_at = created_at
    db_session.add(credit_ledger_record)
    await db_session.flush()
    return credit_ledger_record
