from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.database.orm.llm_call import LlmCallOrm
from libs.generate_text.results import GenerateTextRollupResult


class GenerateTextRollupService:
    """Reads pb_llm_call and aggregates it into a step's or a run's rollup. Writes
    nothing; GenerateTextStepService and GenerateTextRunService record the result."""

    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._db_session_factory = db_session_factory

    async def build_step_rollup(self, step_id: int) -> GenerateTextRollupResult:
        query = select(
            func.count(LlmCallOrm.id),
            func.coalesce(func.sum(LlmCallOrm.input_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.output_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.cost_usd), 0),
        ).where(LlmCallOrm.step_id == step_id)

        async with self._db_session_factory() as db_session:
            query_result = await db_session.execute(query)
            llm_call_count, input_tokens, output_tokens, cost_usd = query_result.one()

        return GenerateTextRollupResult(
            llm_call_count=llm_call_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=Decimal(cost_usd),
        )

    async def build_run_rollup(self, run_id: int) -> GenerateTextRollupResult:
        query = select(
            func.count(LlmCallOrm.id),
            func.coalesce(func.sum(LlmCallOrm.input_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.output_tokens), 0),
            func.coalesce(func.sum(LlmCallOrm.cost_usd), 0),
        ).where(LlmCallOrm.run_id == run_id)

        async with self._db_session_factory() as db_session:
            query_result = await db_session.execute(query)
            llm_call_count, input_tokens, output_tokens, cost_usd = query_result.one()

        return GenerateTextRollupResult(
            llm_call_count=llm_call_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=Decimal(cost_usd),
        )
