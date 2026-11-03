from decimal import Decimal

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.credits.inputs import GrantCreditsInput
from libs.credits.results import FindCreditBalanceResult
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm.credit_ledger import CreditLedgerOrm
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.database.orm.user import UserOrm
from libs.generate_text.types import GenerateTextStepStatusType


class CreditLedgerService:
    """Writes pb_credit_ledger rows and keeps each user's cached balance in step with them;
    never commits, so the caller's transaction owns every write."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def charge_generate_text_step(self, step_id: int) -> None:
        """Charges the step's owner its charge_usd and adds it to the run's charge;
        writes nothing for a free step."""
        # Read what the step charges and who it charges
        step_query = select(
            GenerateTextStepOrm.charge_usd,
            GenerateTextStepOrm.run_id,
            GenerateTextStepOrm.created_by_id,
        ).where(GenerateTextStepOrm.id == step_id)
        step_query_result = await self._db_session.execute(step_query)
        step_row = step_query_result.one_or_none()
        if step_row is None:
            raise NotFoundException(f"Generate text step {step_id} not found")
        charge_usd, run_id, user_id = step_row
        if charge_usd == 0:
            return

        # Record the charge
        charge_insert = insert(CreditLedgerOrm).values(
            user_id=user_id,
            amount_usd=-charge_usd,
            entry_type=CreditLedgerEntryType.CHARGE,
            generate_text_run_id=run_id,
            generate_text_step_id=step_id,
            note=None,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        await self._db_session.execute(charge_insert)

        # Subtract it from the user's balance
        await self._add_to_credit_balance(user_id, -charge_usd)

        # Add it to the run's charge
        run_charge_update = (
            update(GenerateTextRunOrm)
            .where(GenerateTextRunOrm.id == run_id)
            .values(charge_usd=GenerateTextRunOrm.charge_usd + charge_usd)
        )
        await self._db_session.execute(run_charge_update)

    async def refund_failed_generate_text_run_segment(self, run_id: int) -> None:
        """Refunds the charges of the run's steps after its last review step, since a
        failed run resumes from that review; writes nothing when there are none."""
        # Find the last review step, past which the work is lost
        boundary_query = select(func.coalesce(func.max(GenerateTextStepOrm.step_number), 0)).where(
            GenerateTextStepOrm.run_id == run_id,
            or_(
                GenerateTextStepOrm.status == GenerateTextStepStatusType.AWAITING_REVIEW,
                GenerateTextStepOrm.decided_at.is_not(None),
            ),
        )
        boundary_query_result = await self._db_session.execute(boundary_query)
        boundary_step_number = boundary_query_result.scalar_one()

        # Find the charges of the steps after it
        charge_query = (
            select(
                CreditLedgerOrm.user_id,
                CreditLedgerOrm.generate_text_step_id,
                CreditLedgerOrm.amount_usd,
            )
            .join(
                GenerateTextStepOrm,
                GenerateTextStepOrm.id == CreditLedgerOrm.generate_text_step_id,
            )
            .where(
                CreditLedgerOrm.generate_text_run_id == run_id,
                CreditLedgerOrm.entry_type == CreditLedgerEntryType.CHARGE,
                GenerateTextStepOrm.step_number > boundary_step_number,
            )
        )
        charge_query_result = await self._db_session.execute(charge_query)
        charge_rows = charge_query_result.all()
        if not charge_rows:
            return

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
                for user_id, step_id, amount_usd in charge_rows
            ]
        )
        await self._db_session.execute(refund_insert)

        # Add the refunds back to each user's balance
        refund_usd_by_user_id: dict[int, Decimal] = {}
        for user_id, _, amount_usd in charge_rows:
            refund_usd_by_user_id[user_id] = refund_usd_by_user_id.get(user_id, Decimal(0)) - (
                amount_usd
            )
        for user_id, refund_usd in refund_usd_by_user_id.items():
            await self._add_to_credit_balance(user_id, refund_usd)

        # Take them off the run's charge
        total_refund_usd = sum(refund_usd_by_user_id.values(), Decimal(0))
        run_charge_update = (
            update(GenerateTextRunOrm)
            .where(GenerateTextRunOrm.id == run_id)
            .values(charge_usd=GenerateTextRunOrm.charge_usd - total_refund_usd)
        )
        await self._db_session.execute(run_charge_update)

    async def grant_credits(
        self, grant_credits_input: GrantCreditsInput, auth_user: AuthUser
    ) -> None:
        """Grants credits to a user; NotFoundException if the user doesn't exist."""
        # Add to the balance first, so an unknown user fails before a ledger row is written
        await self._add_to_credit_balance(
            grant_credits_input.user_id, grant_credits_input.amount_usd
        )

        # Record the grant
        grant_insert = insert(CreditLedgerOrm).values(
            user_id=grant_credits_input.user_id,
            amount_usd=grant_credits_input.amount_usd,
            entry_type=CreditLedgerEntryType.GRANT,
            generate_text_run_id=None,
            generate_text_step_id=None,
            note=grant_credits_input.note,
            created_by_id=auth_user.id,
            updated_by_id=auth_user.id,
        )
        await self._db_session.execute(grant_insert)

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
