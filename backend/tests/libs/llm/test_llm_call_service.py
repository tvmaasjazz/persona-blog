from decimal import Decimal

import pytest
import structlog.testing
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.llm_call import LlmCallOrm
from libs.llm.exceptions import LlmUnavailableException
from libs.llm.services.llm_call_service import LlmCallService
from libs.llm.settings import LlmTierSettings
from libs.llm.types import LlmCallReasonType, LlmCallStatusType, LlmProviderType, LlmType
from tests.factories.auth import build_auth_user
from tests.factories.llm import build_llm_completion_input, build_llm_provider_completion_result
from tests.factories.users import insert_user_row


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def test_create_pending_llm_call_persists_pending_row_with_null_metrics(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_call_service = LlmCallService(db_session_factory=db_session_factory)
    llm_completion_input = build_llm_completion_input(purpose="pending-purpose")
    tier_settings = LlmTierSettings(
        provider=LlmProviderType.OPENAI,
        model_name="test-model",
        max_output_tokens=2048,
        request_timeout_seconds=30,
    )

    create_pending_llm_call_result = await llm_call_service.create_pending_llm_call(
        llm_completion_input, tier_settings, auth_user
    )

    llm_call_query = select(LlmCallOrm).where(
        LlmCallOrm.identity == create_pending_llm_call_result.llm_call_identity
    )
    llm_call_record = await db_session.scalar(llm_call_query)
    assert llm_call_record is not None
    assert llm_call_record.id == create_pending_llm_call_result.llm_call_id
    assert llm_call_record.status == LlmCallStatusType.PENDING
    assert llm_call_record.llm_type == LlmType.FAST
    assert llm_call_record.provider == LlmProviderType.OPENAI
    assert llm_call_record.model_name == "test-model"
    assert llm_call_record.purpose == "pending-purpose"
    assert llm_call_record.input_tokens is None
    assert llm_call_record.output_tokens is None
    assert llm_call_record.cached_input_tokens is None
    assert llm_call_record.reasoning_tokens is None
    assert llm_call_record.cost_usd is None
    assert llm_call_record.duration_ms is None
    assert llm_call_record.provider_error_message is None
    assert llm_call_record.created_by_id == auth_user.id
    assert llm_call_record.updated_by_id == auth_user.id


async def test_complete_llm_call_updates_row_with_result_and_cost(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_call_service = LlmCallService(db_session_factory=db_session_factory)
    llm_completion_input = build_llm_completion_input(purpose="complete-purpose")
    tier_settings = LlmTierSettings(
        provider=LlmProviderType.OPENAI,
        model_name="test-model",
        max_output_tokens=2048,
        request_timeout_seconds=30,
    )
    create_pending_llm_call_result = await llm_call_service.create_pending_llm_call(
        llm_completion_input, tier_settings, auth_user
    )
    provider_completion_result = build_llm_provider_completion_result(
        content="Hello there.",
        input_tokens=100,
        output_tokens=50,
        cached_input_tokens=20,
        reasoning_tokens=5,
        provider_request_reference="req_complete",
    )

    await llm_call_service.complete_llm_call(
        create_pending_llm_call_result.llm_call_id,
        provider_completion_result,
        cost_usd=Decimal("0.001234"),
        duration_ms=250,
        auth_user=auth_user,
    )

    llm_call_query = select(LlmCallOrm).where(
        LlmCallOrm.identity == create_pending_llm_call_result.llm_call_identity
    )
    llm_call_record = await db_session.scalar(llm_call_query)
    assert llm_call_record is not None
    assert llm_call_record.status == LlmCallStatusType.SUCCEEDED
    assert llm_call_record.reason is None
    assert llm_call_record.response_text == "Hello there."
    assert llm_call_record.input_tokens == 100
    assert llm_call_record.output_tokens == 50
    assert llm_call_record.cached_input_tokens == 20
    assert llm_call_record.reasoning_tokens == 5
    assert llm_call_record.cost_usd == Decimal("0.001234")
    assert llm_call_record.duration_ms == 250
    assert llm_call_record.provider_request_reference == "req_complete"


async def test_complete_llm_call_not_found_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    llm_call_service = LlmCallService(db_session_factory=db_session_factory)
    provider_completion_result = build_llm_provider_completion_result()

    with pytest.raises(NotFoundException):
        await llm_call_service.complete_llm_call(
            999999,
            provider_completion_result,
            cost_usd=Decimal(0),
            duration_ms=1,
            auth_user=build_auth_user(),
        )


async def test_fail_llm_call_llm_exception_writes_reason_and_provider_message(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_call_service = LlmCallService(db_session_factory=db_session_factory)
    llm_completion_input = build_llm_completion_input(purpose="fail-purpose")
    tier_settings = LlmTierSettings(
        provider=LlmProviderType.OPENAI,
        model_name="test-model",
        max_output_tokens=2048,
        request_timeout_seconds=30,
    )
    create_pending_llm_call_result = await llm_call_service.create_pending_llm_call(
        llm_completion_input, tier_settings, auth_user
    )
    llm_provider_exception = LlmUnavailableException(
        "The LLM provider is unavailable", provider_message="upstream said no capacity"
    )

    await llm_call_service.fail_llm_call(
        create_pending_llm_call_result.llm_call_id,
        llm_provider_exception,
        duration_ms=42,
        auth_user=auth_user,
    )

    llm_call_query = select(LlmCallOrm).where(
        LlmCallOrm.identity == create_pending_llm_call_result.llm_call_identity
    )
    llm_call_record = await db_session.scalar(llm_call_query)
    assert llm_call_record is not None
    assert llm_call_record.status == LlmCallStatusType.FAILED
    assert llm_call_record.reason == LlmCallReasonType.PROVIDER_UNAVAILABLE
    assert llm_call_record.error_code == "LlmUnavailableException"
    assert llm_call_record.error_message == "The LLM provider is unavailable"
    assert llm_call_record.provider_error_message == "upstream said no capacity"
    assert llm_call_record.duration_ms == 42


async def test_fail_llm_call_non_llm_exception_records_provider_error_reason_no_message(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_call_service = LlmCallService(db_session_factory=db_session_factory)
    llm_completion_input = build_llm_completion_input(purpose="generic-fail-purpose")
    tier_settings = LlmTierSettings(
        provider=LlmProviderType.OPENAI,
        model_name="test-model",
        max_output_tokens=2048,
        request_timeout_seconds=30,
    )
    create_pending_llm_call_result = await llm_call_service.create_pending_llm_call(
        llm_completion_input, tier_settings, auth_user
    )

    await llm_call_service.fail_llm_call(
        create_pending_llm_call_result.llm_call_id,
        ValueError("boom"),
        duration_ms=7,
        auth_user=auth_user,
    )

    llm_call_query = select(LlmCallOrm).where(
        LlmCallOrm.identity == create_pending_llm_call_result.llm_call_identity
    )
    llm_call_record = await db_session.scalar(llm_call_query)
    assert llm_call_record is not None
    assert llm_call_record.status == LlmCallStatusType.FAILED
    assert llm_call_record.reason == LlmCallReasonType.PROVIDER_ERROR
    assert llm_call_record.error_code == "ValueError"
    assert llm_call_record.error_message == "boom"
    assert llm_call_record.provider_error_message is None


async def test_fail_llm_call_missing_row_logs_warning_and_returns(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    llm_call_service = LlmCallService(db_session_factory=db_session_factory)

    with structlog.testing.capture_logs() as captured_log_events:
        await llm_call_service.fail_llm_call(
            999999,
            ValueError("boom"),
            duration_ms=1,
            auth_user=build_auth_user(),
        )

    llm_call_row_missing_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "llm_call_row_missing"
    ]
    assert len(llm_call_row_missing_events) == 1
    assert llm_call_row_missing_events[0]["llm_call_id"] == 999999
