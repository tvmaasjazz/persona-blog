from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.exceptions import NotFoundException
from libs.credits.inputs import ChargeCreditsInput
from libs.credits.services import CreditLedgerService
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.types import GenerateTextStepStatusType


class GenerateTextCreditService:
    """Charges a run's steps to their owner and refunds the ones a failure loses, through the
    credit ledger, keeping the run's charge in step; never commits, so the caller's
    transaction owns every write."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session
        self._credit_ledger_service = CreditLedgerService(db_session=db_session)

    async def charge_step(self, step_id: int) -> None:
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

        # Charge the user
        charge_credits_input = ChargeCreditsInput(
            user_id=user_id,
            amount_usd=charge_usd,
            generate_text_run_id=run_id,
            generate_text_step_id=step_id,
        )
        await self._credit_ledger_service.charge_credits(charge_credits_input)

        # Add it to the run's charge
        run_charge_update = (
            update(GenerateTextRunOrm)
            .where(GenerateTextRunOrm.id == run_id)
            .values(charge_usd=GenerateTextRunOrm.charge_usd + charge_usd)
        )
        await self._db_session.execute(run_charge_update)

    async def refund_failed_run_segment(self, run_id: int) -> None:
        """Refunds the charges of the run's steps after its last review step, since a failed
        run resumes from that review, and takes them off the run's charge."""
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

        # Find the steps after it
        lost_step_query = select(GenerateTextStepOrm.id).where(
            GenerateTextStepOrm.run_id == run_id,
            GenerateTextStepOrm.step_number > boundary_step_number,
        )
        lost_step_query_result = await self._db_session.execute(lost_step_query)
        lost_step_ids = list(lost_step_query_result.scalars().all())
        if not lost_step_ids:
            return

        # Refund their charges; the ledger skips any already refunded
        refund_charges_result = await self._credit_ledger_service.refund_charges(lost_step_ids)
        if refund_charges_result.refund_usd == 0:
            return

        # Take the refund off the run's charge
        run_charge_update = (
            update(GenerateTextRunOrm)
            .where(GenerateTextRunOrm.id == run_id)
            .values(charge_usd=GenerateTextRunOrm.charge_usd - refund_charges_result.refund_usd)
        )
        await self._db_session.execute(run_charge_update)
