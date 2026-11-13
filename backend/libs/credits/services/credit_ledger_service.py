from decimal import Decimal

from sqlalchemy import exists, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from libs.core.exceptions import NotFoundException
from libs.credits.inputs import ChargeCreditsInput, GrantCreditsInput
from libs.credits.results import (
    FindCreditBalanceResult,
    GrantCreditsResult,
    RefundChargesResult,
)
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm.credit_ledger import CreditLedgerOrm
from libs.database.orm.user import UserOrm


class CreditLedgerService:
    """Writes psg_credit_ledger rows and keeps each user's cached balance in step with them;
    never commits, so the caller's transaction owns every write."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def charge_credits(self, charge_credits_input: ChargeCreditsInput) -> None:
        """Records a charge for a generate text step and lowers the user's balance by it;
        NotFoundException if the user doesn't exist."""
        # Subtract it from the balance first, so an unknown user fails before a ledger row is
        # written
        user_id = charge_credits_input.user_id
        await self._add_to_credit_balance(user_id, -charge_credits_input.amount_usd)

        # Record the charge
        charge_insert = insert(CreditLedgerOrm).values(
            user_id=user_id,
            amount_usd=-charge_credits_input.amount_usd,
            entry_type=CreditLedgerEntryType.CHARGE,
            generate_text_run_id=charge_credits_input.generate_text_run_id,
            generate_text_step_id=charge_credits_input.generate_text_step_id,
            note=None,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        await self._db_session.execute(charge_insert)

    async def refund_charges(self, generate_text_step_ids: list[int]) -> RefundChargesResult:
        """Refunds the steps' charges and returns the total; a charge already refunded is
        skipped, so a second call refunds nothing."""
        # Find the steps' unrefunded charges
        refund_ledger = aliased(CreditLedgerOrm)
        refund_exists = exists().where(
            refund_ledger.generate_text_step_id == CreditLedgerOrm.generate_text_step_id,
            refund_ledger.entry_type == CreditLedgerEntryType.REFUND,
        )
        charge_query = select(
            CreditLedgerOrm.user_id,
            CreditLedgerOrm.generate_text_run_id,
            CreditLedgerOrm.generate_text_step_id,
            CreditLedgerOrm.amount_usd,
        ).where(
            CreditLedgerOrm.generate_text_step_id.in_(generate_text_step_ids),
            CreditLedgerOrm.entry_type == CreditLedgerEntryType.CHARGE,
            ~refund_exists,
        )
        charge_query_result = await self._db_session.execute(charge_query)
        charge_rows = charge_query_result.all()
        if not charge_rows:
            return RefundChargesResult(refund_usd=Decimal(0))

        # Record one refund per charge
        refund_insert = insert(CreditLedgerOrm).values(
            [
                {
                    "user_id": user_id,
                    "amount_usd": -amount_usd,
                    "entry_type": CreditLedgerEntryType.REFUND,
                    "generate_text_run_id": run_id,
                    "generate_text_step_id": step_id,
                    "note": None,
                    "created_by_id": user_id,
                    "updated_by_id": user_id,
                }
                for user_id, run_id, step_id, amount_usd in charge_rows
            ]
        )
        await self._db_session.execute(refund_insert)

        # Add the refunds back to each user's balance
        refund_usd_by_user_id: dict[int, Decimal] = {}
        for user_id, _, _, amount_usd in charge_rows:
            refund_usd_by_user_id[user_id] = refund_usd_by_user_id.get(user_id, Decimal(0)) - (
                amount_usd
            )
        for user_id, refund_usd in refund_usd_by_user_id.items():
            await self._add_to_credit_balance(user_id, refund_usd)

        return RefundChargesResult(refund_usd=sum(refund_usd_by_user_id.values(), Decimal(0)))

    async def grant_credits(
        self, grant_credits_input: GrantCreditsInput, granted_by_id: int
    ) -> GrantCreditsResult:
        """Grants credits to a user, recorded as made by the given user, and returns the grant's
        identity; NotFoundException if the user doesn't exist."""
        # Add to the balance first, so an unknown user fails before a ledger row is written
        await self._add_to_credit_balance(
            grant_credits_input.user_id, grant_credits_input.amount_usd
        )

        # Record the grant
        grant_insert = (
            insert(CreditLedgerOrm)
            .values(
                user_id=grant_credits_input.user_id,
                amount_usd=grant_credits_input.amount_usd,
                entry_type=CreditLedgerEntryType.GRANT,
                generate_text_run_id=None,
                generate_text_step_id=None,
                invite_id=grant_credits_input.invite_id,
                note=grant_credits_input.note,
                created_by_id=granted_by_id,
                updated_by_id=granted_by_id,
            )
            .returning(CreditLedgerOrm.identity)
        )
        grant_insert_result = await self._db_session.execute(grant_insert)
        grant_identity = grant_insert_result.scalar_one()

        return GrantCreditsResult(identity=grant_identity)

    async def find_credit_balance(self, user_id: int) -> FindCreditBalanceResult:
        """Returns the user's cached credit balance; NotFoundException if there is no user."""
        credit_balance_query = select(UserOrm.credit_balance_usd).where(UserOrm.id == user_id)
        credit_balance_query_result = await self._db_session.execute(credit_balance_query)
        credit_balance_usd = credit_balance_query_result.scalar_one_or_none()

        if credit_balance_usd is None:
            raise NotFoundException(f"User {user_id} not found")
        return FindCreditBalanceResult(credit_balance_usd=credit_balance_usd)

    async def _add_to_credit_balance(self, user_id: int, amount_usd: Decimal) -> None:
        # A SQL expression, so two writers can't overwrite each other's balance
        credit_balance_update = (
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(credit_balance_usd=UserOrm.credit_balance_usd + amount_usd)
        )
        credit_balance_update_result = await self._db_session.execute(credit_balance_update)
        if credit_balance_update_result.rowcount == 0:
            raise NotFoundException(f"User {user_id} not found")
