from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_rollup_service import GenerateTextRollupService
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import (
    GenerateTextNodeType,
    GenerateTextRunStatusType,
    GenerateTextStepStatusType,
)
from tests.factories.auth import build_auth_user
from tests.factories.generate_text import (
    build_create_generate_text_run_input,
    build_generate_text_state,
)
from tests.factories.llm import insert_llm_call_row
from tests.factories.users import insert_user_row


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


def _build_instrumentation_service(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> tuple[GenerateTextRunService, GenerateTextInstrumentationService]:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    rollup_service = GenerateTextRollupService(db_session_factory=db_session_factory)
    instrumentation_service = GenerateTextInstrumentationService(
        run_service=run_service, step_service=step_service, rollup_service=rollup_service
    )
    return run_service, instrumentation_service


async def test_instrument_writes_completed_step_and_rolls_up_run_and_step(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service, instrumentation_service = _build_instrumentation_service(db_session_factory)
    create_run_result = await run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )
    generate_text_state = build_generate_text_state(
        auth_user_id=auth_user.id,
        auth_user_identity=auth_user.identity,
        generate_text_run_id=create_run_result.id,
        generate_text_run_identity=create_run_result.identity,
    )
    received_states: list[GenerateTextState] = []

    async def node(state: GenerateTextState) -> dict[str, Any]:
        received_states.append(state)
        await insert_llm_call_row(
            db_session,
            created_by_id=auth_user.id,
            run_id=state.generate_text_run_id,
            step_id=state.current_step_id,
            input_tokens=10,
            output_tokens=5,
            cost_usd=Decimal("0.001"),
        )
        await db_session.commit()
        return {
            "step_outputs": {
                **state.step_outputs,
                GenerateTextNodeType.GENERATE_DRAFT.value: "A draft.",
            }
        }

    instrumented_node = instrumentation_service.instrument(
        GenerateTextNodeType.GENERATE_DRAFT, node
    )

    node_result = await instrumented_node(generate_text_state)

    step_query = select(GenerateTextStepOrm).where(
        GenerateTextStepOrm.run_id == create_run_result.id
    )
    step_record = await db_session.scalar(step_query)
    run_record = await db_session.get(GenerateTextRunOrm, create_run_result.id)
    assert node_result == {"step_outputs": {"GENERATE_DRAFT": "A draft."}}
    assert step_record is not None
    assert step_record.status == GenerateTextStepStatusType.SUCCEEDED
    assert step_record.output == {"text": "A draft."}
    assert step_record.llm_call_count == 1
    assert step_record.input_tokens == 10
    assert step_record.output_tokens == 5
    assert step_record.cost_usd == Decimal("0.001")
    assert run_record is not None
    assert run_record.current_step == "GENERATE_DRAFT"
    assert run_record.llm_call_count == 1
    assert run_record.input_tokens == 10
    assert run_record.output_tokens == 5
    assert run_record.cost_usd == Decimal("0.001")
    assert len(received_states) == 1
    assert received_states[0].current_step_id == step_record.id


async def test_instrument_node_raises_leaves_failed_step_and_failed_run(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_service, instrumentation_service = _build_instrumentation_service(db_session_factory)
    create_run_result = await run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )
    generate_text_state = build_generate_text_state(
        auth_user_id=auth_user.id,
        auth_user_identity=auth_user.identity,
        generate_text_run_id=create_run_result.id,
        generate_text_run_identity=create_run_result.identity,
    )

    async def failing_node(state: GenerateTextState) -> dict[str, Any]:
        raise ValueError("boom")

    instrumented_node = instrumentation_service.instrument(
        GenerateTextNodeType.GENERATE_DRAFT, failing_node
    )

    with pytest.raises(ValueError):
        await instrumented_node(generate_text_state)

    step_query = select(GenerateTextStepOrm).where(
        GenerateTextStepOrm.run_id == create_run_result.id
    )
    step_record = await db_session.scalar(step_query)
    run_record = await db_session.get(GenerateTextRunOrm, create_run_result.id)
    assert step_record is not None
    assert step_record.status == GenerateTextStepStatusType.FAILED
    assert step_record.error_code == "ValueError"
    assert step_record.error_message == "boom"
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "ValueError"
    assert run_record.error_message == "boom"
    assert run_record.error_step == "GENERATE_DRAFT"
