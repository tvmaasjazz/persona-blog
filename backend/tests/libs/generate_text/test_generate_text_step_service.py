from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.results import FindLatestGenerateTextStepResult
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.types import GenerateTextStepStatusType, HumanDecisionType
from tests.factories.auth import build_auth_user
from tests.factories.database import fetch_database_utc_now
from tests.factories.generate_text import (
    build_create_generate_text_run_input,
    build_create_generate_text_step_input,
    insert_generate_text_step_row,
)
from tests.factories.llm import insert_llm_call_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def _insert_run_id(
    db_session: AsyncSession, run_service: GenerateTextRunService, auth_user: AuthUser
) -> int:
    persona_record = await insert_persona_row(db_session, created_by_id=auth_user.id)
    await db_session.commit()
    create_run_result = await run_service.create_run(
        build_create_generate_text_run_input(persona_id=persona_record.id), auth_user
    )
    return create_run_result.id


async def test_create_step_persists_first_step_number_and_attempt(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    create_generate_text_step_input = build_create_generate_text_step_input(
        run_id=run_id, step_name="GENERATE_DRAFT"
    )

    create_step_result = await step_service.create_step(create_generate_text_step_input, auth_user)

    step_query = select(GenerateTextStepOrm).where(GenerateTextStepOrm.id == create_step_result.id)
    step_record = await db_session.scalar(step_query)
    assert step_record is not None
    assert step_record.identity == create_step_result.identity
    assert step_record.run_id == run_id
    assert step_record.step_number == 1
    assert step_record.attempt == 1
    assert step_record.step_name == "GENERATE_DRAFT"
    assert step_record.status == GenerateTextStepStatusType.RUNNING
    assert step_record.started_at is not None
    assert step_record.created_by_id == auth_user.id
    assert step_record.updated_by_id == auth_user.id


async def test_create_step_step_number_increments_per_run(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)

    first_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="GENERATE_OUTLINE"),
        auth_user,
    )
    second_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="GENERATE_DRAFT"), auth_user
    )

    first_step_record = await db_session.get(GenerateTextStepOrm, first_step_result.id)
    second_step_record = await db_session.get(GenerateTextStepOrm, second_step_result.id)
    assert first_step_record is not None
    assert second_step_record is not None
    assert first_step_record.step_number == 1
    assert second_step_record.step_number == 2


async def test_create_step_attempt_increments_per_repeated_step_name(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)

    first_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="GENERATE_DRAFT"), auth_user
    )
    second_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="GENERATE_DRAFT"), auth_user
    )

    first_step_record = await db_session.get(GenerateTextStepOrm, first_step_result.id)
    second_step_record = await db_session.get(GenerateTextStepOrm, second_step_result.id)
    assert first_step_record is not None
    assert second_step_record is not None
    assert first_step_record.attempt == 1
    assert second_step_record.attempt == 2
    assert second_step_record.step_number == 2


async def test_create_step_awaiting_review_step_resumes_instead_of_duplicating(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    create_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="REVIEW_DRAFT"), auth_user
    )
    await step_service.record_awaiting_review(create_step_result.id, 10)

    resumed_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="REVIEW_DRAFT"), auth_user
    )

    assert resumed_step_result.id == create_step_result.id
    step_record = await db_session.get(GenerateTextStepOrm, create_step_result.id)
    assert step_record is not None
    assert step_record.status == GenerateTextStepStatusType.RUNNING


async def test_complete_step_sets_succeeded_status_output_and_zero_rollup_when_no_calls(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    create_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id), auth_user
    )

    await step_service.complete_step(create_step_result.id, "A draft about coffee.", 250)

    step_record = await db_session.get(GenerateTextStepOrm, create_step_result.id)
    assert step_record is not None
    assert step_record.status == GenerateTextStepStatusType.SUCCEEDED
    assert step_record.output == {"text": "A draft about coffee."}
    assert step_record.duration_ms == 250
    assert step_record.finished_at is not None
    assert step_record.llm_call_count == 0
    assert step_record.input_tokens == 0
    assert step_record.output_tokens == 0
    assert step_record.cost_usd == Decimal("0")


async def test_complete_step_sums_llm_calls_coalescing_null_tokens_and_cost(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    create_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id), auth_user
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=auth_user.id,
        run_id=run_id,
        step_id=create_step_result.id,
        input_tokens=100,
        output_tokens=50,
        cost_usd=Decimal("0.01"),
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=auth_user.id,
        run_id=run_id,
        step_id=create_step_result.id,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
    )
    await db_session.commit()

    await step_service.complete_step(create_step_result.id, "A draft about coffee.", 250)

    step_record = await db_session.get(GenerateTextStepOrm, create_step_result.id)
    assert step_record is not None
    assert step_record.llm_call_count == 2
    assert step_record.input_tokens == 100
    assert step_record.output_tokens == 50
    assert step_record.cost_usd == Decimal("0.01")


async def test_fail_step_sets_failed_status_and_error_fields(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    create_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id), auth_user
    )

    await step_service.fail_step(create_step_result.id, "ValueError", "boom", 42)

    step_record = await db_session.get(GenerateTextStepOrm, create_step_result.id)
    assert step_record is not None
    assert step_record.status == GenerateTextStepStatusType.FAILED
    assert step_record.error_code == "ValueError"
    assert step_record.error_message == "boom"
    assert step_record.duration_ms == 42
    assert step_record.finished_at is not None


async def test_record_decision_sets_human_decision_and_feedback(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    create_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id), auth_user
    )

    await step_service.record_decision(
        create_step_result.id, HumanDecisionType.APPROVED, "Looks good.", auth_user
    )

    database_utc_now = await fetch_database_utc_now(db_session)
    step_record = await db_session.get(GenerateTextStepOrm, create_step_result.id)
    assert step_record is not None
    assert step_record.human_decision == HumanDecisionType.APPROVED
    assert step_record.human_feedback == "Looks good."
    assert step_record.decided_by_id == auth_user.id
    assert step_record.decided_at == database_utc_now


async def test_record_awaiting_review_sets_awaiting_review_status_and_duration(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    create_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="REVIEW_DRAFT"), auth_user
    )

    await step_service.record_awaiting_review(create_step_result.id, 120)

    step_record = await db_session.get(GenerateTextStepOrm, create_step_result.id)
    assert step_record is not None
    assert step_record.status == GenerateTextStepStatusType.AWAITING_REVIEW
    assert step_record.duration_ms == 120


async def test_record_awaiting_review_not_found_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)

    with pytest.raises(NotFoundException):
        await step_service.record_awaiting_review(999999, 1)


async def test_find_latest_step_returns_newest_step_name_and_content(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    first_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="GENERATE_OUTLINE"),
        auth_user,
    )
    await step_service.complete_step(first_step_result.id, "An outline.", 10)
    second_step_result = await step_service.create_step(
        build_create_generate_text_step_input(run_id=run_id, step_name="GENERATE_DRAFT"), auth_user
    )
    await step_service.complete_step(second_step_result.id, "A draft.", 20)

    find_latest_step_result = await step_service.find_latest_step(run_id)

    assert find_latest_step_result == FindLatestGenerateTextStepResult(
        step_name="GENERATE_DRAFT", content="A draft."
    )


async def test_find_latest_step_output_null_returns_empty_content(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    await insert_generate_text_step_row(
        db_session,
        run_id=run_id,
        created_by_id=auth_user.id,
        step_name="GENERATE_OUTLINE",
        status=GenerateTextStepStatusType.RUNNING,
    )
    await db_session.commit()

    find_latest_step_result = await step_service.find_latest_step(run_id)

    assert find_latest_step_result == FindLatestGenerateTextStepResult(
        step_name="GENERATE_OUTLINE", content=""
    )


async def test_find_latest_step_no_steps_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)

    with pytest.raises(NotFoundException):
        await step_service.find_latest_step(999999)


async def test_complete_step_not_found_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)

    with pytest.raises(NotFoundException):
        await step_service.complete_step(999999, "output", 1)


async def test_find_awaiting_review_step_id_returns_paused_step_id(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    await insert_generate_text_step_row(
        db_session,
        run_id=run_id,
        created_by_id=auth_user.id,
        step_number=1,
        step_name="GENERATE_DRAFT",
        status=GenerateTextStepStatusType.SUCCEEDED,
    )
    paused_step_record = await insert_generate_text_step_row(
        db_session,
        run_id=run_id,
        created_by_id=auth_user.id,
        step_number=2,
        step_name="REVIEW_DRAFT",
        status=GenerateTextStepStatusType.AWAITING_REVIEW,
    )
    await db_session.commit()

    awaiting_review_step_id = await step_service.find_awaiting_review_step_id(run_id)

    assert awaiting_review_step_id == paused_step_record.id


async def test_find_awaiting_review_step_id_no_paused_step_returns_none(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    run_id = await _insert_run_id(db_session, run_service, auth_user)
    await insert_generate_text_step_row(
        db_session,
        run_id=run_id,
        created_by_id=auth_user.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
    )
    await db_session.commit()

    awaiting_review_step_id = await step_service.find_awaiting_review_step_id(run_id)

    assert awaiting_review_step_id is None
