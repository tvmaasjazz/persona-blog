from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.generate_text.results import GenerateTextRollupResult
from libs.generate_text.services.generate_text_rollup_service import GenerateTextRollupService
from tests.factories.generate_text import (
    insert_generate_text_run_row,
    insert_generate_text_step_row,
)
from tests.factories.llm import insert_llm_call_row
from tests.factories.users import insert_user_row


async def test_build_step_rollup_sums_calls_coalescing_null_tokens_and_cost(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=user_record.id,
        run_id=run_record.id,
        step_id=step_record.id,
        input_tokens=100,
        output_tokens=50,
        cost_usd=Decimal("0.01"),
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=user_record.id,
        run_id=run_record.id,
        step_id=step_record.id,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
    )
    await db_session.commit()
    generate_text_rollup_service = GenerateTextRollupService(db_session_factory=db_session_factory)

    step_rollup_result = await generate_text_rollup_service.build_step_rollup(step_record.id)

    assert step_rollup_result == GenerateTextRollupResult(
        llm_call_count=2, input_tokens=100, output_tokens=50, cost_usd=Decimal("0.01")
    )


async def test_build_step_rollup_no_calls_returns_zeroes(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_record = await insert_generate_text_step_row(
        db_session, run_id=run_record.id, created_by_id=user_record.id
    )
    await db_session.commit()
    generate_text_rollup_service = GenerateTextRollupService(db_session_factory=db_session_factory)

    step_rollup_result = await generate_text_rollup_service.build_step_rollup(step_record.id)

    assert step_rollup_result == GenerateTextRollupResult(
        llm_call_count=0, input_tokens=0, output_tokens=0, cost_usd=Decimal("0")
    )


async def test_build_run_rollup_sums_calls_across_steps(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    step_one_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        seq=1,
        step_name="GENERATE_OUTLINE",
    )
    step_two_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_record.id,
        created_by_id=user_record.id,
        seq=2,
        step_name="GENERATE_DRAFT",
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=user_record.id,
        run_id=run_record.id,
        step_id=step_one_record.id,
        input_tokens=100,
        output_tokens=50,
        cost_usd=Decimal("0.01"),
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=user_record.id,
        run_id=run_record.id,
        step_id=step_two_record.id,
        input_tokens=200,
        output_tokens=80,
        cost_usd=Decimal("0.02"),
    )
    await db_session.commit()
    generate_text_rollup_service = GenerateTextRollupService(db_session_factory=db_session_factory)

    run_rollup_result = await generate_text_rollup_service.build_run_rollup(run_record.id)

    assert run_rollup_result == GenerateTextRollupResult(
        llm_call_count=2, input_tokens=300, output_tokens=130, cost_usd=Decimal("0.03")
    )


async def test_build_run_rollup_no_calls_returns_zeroes(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    run_record = await insert_generate_text_run_row(db_session, created_by_id=user_record.id)
    await db_session.commit()
    generate_text_rollup_service = GenerateTextRollupService(db_session_factory=db_session_factory)

    run_rollup_result = await generate_text_rollup_service.build_run_rollup(run_record.id)

    assert run_rollup_result == GenerateTextRollupResult(
        llm_call_count=0, input_tokens=0, output_tokens=0, cost_usd=Decimal("0")
    )
