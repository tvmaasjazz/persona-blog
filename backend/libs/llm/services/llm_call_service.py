from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.llm_call import LlmCallOrm
from libs.llm.exceptions import LlmException
from libs.llm.inputs import LlmCompletionInput
from libs.llm.results import CreatePendingLlmCallResult, LlmProviderCompletionResult
from libs.llm.settings import LlmTierSettings
from libs.llm.types import LlmCallReasonType, LlmCallStatusType
from libs.llm.utils import LlmUtils

logger = structlog.get_logger(__name__)


class LlmCallService:
    """Owns every write to pb_llm_call. Each write opens its own session and commits in its
    own transaction, so a row survives the caller's rollback. See fastapi-structure.md,
    Services > Records that must survive a rollback."""

    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._db_session_factory = db_session_factory

    async def create_pending_llm_call(
        self,
        llm_completion_input: LlmCompletionInput,
        tier_settings: LlmTierSettings,
        auth_user: AuthUser,
    ) -> CreatePendingLlmCallResult:
        async with self._db_session_factory() as db_session, db_session.begin():
            llm_call_record = LlmCallOrm(
                llm_type=llm_completion_input.llm_type,
                provider=tier_settings.provider,
                model_name=tier_settings.model_name,
                purpose=llm_completion_input.purpose,
                system_prompt=llm_completion_input.system_prompt,
                user_prompt=llm_completion_input.user_prompt,
                run_id=llm_completion_input.run_id,
                step_id=llm_completion_input.step_id,
                status=LlmCallStatusType.PENDING,
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            db_session.add(llm_call_record)
            await db_session.flush()
            llm_call_id = llm_call_record.id
            llm_call_identity = llm_call_record.identity

        return CreatePendingLlmCallResult(
            llm_call_id=llm_call_id, llm_call_identity=llm_call_identity
        )

    async def complete_llm_call(
        self,
        llm_call_id: int,
        provider_completion_result: LlmProviderCompletionResult,
        cost_usd: Decimal,
        duration_ms: int,
        auth_user: AuthUser,
    ) -> None:
        response_json: dict[str, Any] | None = None
        if provider_completion_result.parsed_output is not None:
            response_json = provider_completion_result.parsed_output.model_dump(mode="json")

        call_status = LlmUtils.resolve_status(provider_completion_result.reason)

        async with self._db_session_factory() as db_session, db_session.begin():
            llm_call_record = await db_session.get(LlmCallOrm, llm_call_id)
            if llm_call_record is None:
                raise NotFoundException(f"LLM call {llm_call_id} not found")

            llm_call_record.status = call_status
            llm_call_record.reason = provider_completion_result.reason
            llm_call_record.response_text = provider_completion_result.content
            llm_call_record.response_json = response_json
            llm_call_record.input_tokens = provider_completion_result.input_tokens
            llm_call_record.output_tokens = provider_completion_result.output_tokens
            llm_call_record.cached_input_tokens = provider_completion_result.cached_input_tokens
            llm_call_record.reasoning_tokens = provider_completion_result.reasoning_tokens
            llm_call_record.cost_usd = cost_usd
            llm_call_record.duration_ms = duration_ms
            llm_call_record.provider_request_reference = (
                provider_completion_result.provider_request_reference
            )
            llm_call_record.updated_by_id = auth_user.id
            await db_session.flush()

    async def fail_llm_call(
        self,
        llm_call_id: int,
        llm_provider_exception: Exception,
        duration_ms: int,
        auth_user: AuthUser,
    ) -> None:
        async with self._db_session_factory() as db_session, db_session.begin():
            llm_call_record = await db_session.get(LlmCallOrm, llm_call_id)
            if llm_call_record is None:
                # The provider error is already on its way up; losing its row is not worth
                # replacing it with a second exception.
                logger.warning("llm_call_row_missing", llm_call_id=llm_call_id)
                return

            failure_reason = (
                llm_provider_exception.reason
                if isinstance(llm_provider_exception, LlmException)
                else LlmCallReasonType.PROVIDER_ERROR
            )
            provider_message = (
                llm_provider_exception.provider_message
                if isinstance(llm_provider_exception, LlmException)
                else None
            )
            llm_call_record.status = LlmUtils.resolve_status(failure_reason)
            llm_call_record.reason = failure_reason
            llm_call_record.error_code = type(llm_provider_exception).__name__
            llm_call_record.error_message = str(llm_provider_exception)
            llm_call_record.provider_error_message = provider_message
            llm_call_record.duration_ms = duration_ms
            llm_call_record.updated_by_id = auth_user.id
            await db_session.flush()
