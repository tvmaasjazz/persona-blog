import time
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.llm_call import LlmCallOrm
from libs.llm.constants import EXCEPTION_BY_REASON, STATUS_BY_REASON
from libs.llm.exceptions import LlmException, LlmUnavailableException
from libs.llm.inputs import LlmCompletionInput, LlmProviderCompletionInput
from libs.llm.results import (
    LlmCompletionResult,
    LlmProviderCompletionResult,
    LlmStructuredCompletionResult,
)
from libs.llm.services.llm_provider_service import LlmProviderService
from libs.llm.settings import LlmSettings, LlmTierSettings
from libs.llm.types import LlmCallReasonType, LlmCallStatusType, LlmProviderType, LlmType

logger = structlog.get_logger(__name__)


class LlmService:
    def __init__(
        self,
        llm_provider_services: dict[LlmProviderType, LlmProviderService],
        db_session_factory: async_sessionmaker[AsyncSession],
        llm_settings: LlmSettings,
    ) -> None:
        self._llm_provider_services = llm_provider_services
        self._db_session_factory = db_session_factory
        self._llm_settings = llm_settings

    async def complete(
        self, llm_completion_input: LlmCompletionInput, auth_user: AuthUser
    ) -> LlmCompletionResult:
        provider_completion_result, llm_call_identity = await self._complete(
            llm_completion_input, auth_user, output_type=None
        )
        return LlmCompletionResult(
            llm_call_identity=llm_call_identity,
            content=provider_completion_result.content,
            input_tokens=provider_completion_result.input_tokens,
            output_tokens=provider_completion_result.output_tokens,
        )

    async def complete_structured[T: BaseModel](
        self,
        llm_completion_input: LlmCompletionInput,
        output_type: type[T],
        auth_user: AuthUser,
    ) -> LlmStructuredCompletionResult[T]:
        provider_completion_result, llm_call_identity = await self._complete(
            llm_completion_input, auth_user, output_type=output_type
        )
        if provider_completion_result.parsed_output is None:
            raise LlmUnavailableException("The model returned no structured output")

        return LlmStructuredCompletionResult[T](
            llm_call_identity=llm_call_identity,
            output=provider_completion_result.parsed_output,
            input_tokens=provider_completion_result.input_tokens,
            output_tokens=provider_completion_result.output_tokens,
        )

    async def _complete(
        self,
        llm_completion_input: LlmCompletionInput,
        auth_user: AuthUser,
        output_type: type[BaseModel] | None,
    ) -> tuple[LlmProviderCompletionResult, UUID]:
        tier_settings = self._resolve_tier(llm_completion_input.llm_type)
        llm_provider_service = self._resolve_provider_service(tier_settings.provider)

        llm_call_id, llm_call_identity = await self._create_pending_llm_call(
            llm_completion_input, tier_settings, auth_user
        )

        provider_input = LlmProviderCompletionInput(
            model_name=tier_settings.model_name,
            system_prompt=llm_completion_input.system_prompt,
            user_prompt=llm_completion_input.user_prompt,
            max_output_tokens=tier_settings.max_output_tokens,
            request_timeout_seconds=tier_settings.request_timeout_seconds,
        )

        start_time = time.perf_counter()
        try:
            if output_type is None:
                provider_completion_result = await llm_provider_service.complete(provider_input)
            else:
                provider_completion_result = await llm_provider_service.complete_structured(
                    provider_input, output_type
                )
        except Exception as llm_provider_exception:
            latency_ms = self._elapsed_ms(start_time)
            await self._update_llm_call_failed(
                llm_call_id, llm_provider_exception, latency_ms, auth_user
            )
            raise
        latency_ms = self._elapsed_ms(start_time)

        await self._finish_llm_call(
            llm_call_id,
            llm_completion_input,
            tier_settings,
            provider_completion_result,
            latency_ms,
            auth_user,
        )

        # The row is written first, so a call that produced no usable output is still on
        # record with its tokens and cost before the exception leaves this method.
        if provider_completion_result.reason is not None:
            raise self._build_reason_exception(provider_completion_result.reason)

        return provider_completion_result, llm_call_identity

    @staticmethod
    def _build_reason_exception(reason: LlmCallReasonType) -> LlmException:
        exception_class = EXCEPTION_BY_REASON.get(reason)
        if exception_class is None:
            raise NotImplementedError(f"No exception registered for {reason}")
        return exception_class()

    @staticmethod
    def _resolve_status(reason: LlmCallReasonType | None) -> LlmCallStatusType:
        if reason is None:
            return LlmCallStatusType.SUCCEEDED
        call_status = STATUS_BY_REASON.get(reason)
        if call_status is None:
            raise NotImplementedError(f"No status registered for {reason}")
        return call_status

    def _resolve_tier(self, llm_type: LlmType) -> LlmTierSettings:
        tier_settings = self._llm_settings.tiers.get(llm_type)
        if tier_settings is None:
            raise NotImplementedError(f"No tier configured for {llm_type}")
        return tier_settings

    def _resolve_provider_service(self, provider: LlmProviderType) -> LlmProviderService:
        llm_provider_service = self._llm_provider_services.get(provider)
        if llm_provider_service is None:
            raise NotImplementedError(f"No provider service registered for {provider}")
        return llm_provider_service

    @staticmethod
    def _elapsed_ms(start_time: float) -> int:
        return int((time.perf_counter() - start_time) * 1000)

    def _compute_cost(
        self, model_name: str, input_tokens: int, output_tokens: int, cached_input_tokens: int
    ) -> Decimal:
        model_pricing = self._llm_settings.model_pricing.get(model_name)
        if model_pricing is None:
            logger.warning("llm_pricing_missing", model_name=model_name)
            return Decimal(0)

        billed_input_tokens = input_tokens - cached_input_tokens
        million_tokens = Decimal(1_000_000)
        return (
            billed_input_tokens * model_pricing.input_usd_per_million_tokens
            + cached_input_tokens * model_pricing.cached_input_usd_per_million_tokens
            + output_tokens * model_pricing.output_usd_per_million_tokens
        ) / million_tokens

    async def _create_pending_llm_call(
        self,
        llm_completion_input: LlmCompletionInput,
        tier_settings: LlmTierSettings,
        auth_user: AuthUser,
    ) -> tuple[int, UUID]:
        async with self._db_session_factory() as db_session, db_session.begin():
            llm_call_record = LlmCallOrm(
                llm_type=llm_completion_input.llm_type,
                provider=tier_settings.provider,
                model_name=tier_settings.model_name,
                purpose=llm_completion_input.purpose,
                system_prompt=llm_completion_input.system_prompt,
                user_prompt=llm_completion_input.user_prompt,
                status=LlmCallStatusType.PENDING,
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            db_session.add(llm_call_record)
            await db_session.flush()
            llm_call_id = llm_call_record.id
            llm_call_identity = llm_call_record.identity

        return llm_call_id, llm_call_identity

    async def _finish_llm_call(
        self,
        llm_call_id: int,
        llm_completion_input: LlmCompletionInput,
        tier_settings: LlmTierSettings,
        provider_completion_result: LlmProviderCompletionResult,
        latency_ms: int,
        auth_user: AuthUser,
    ) -> None:
        cost_usd = self._compute_cost(
            tier_settings.model_name,
            provider_completion_result.input_tokens,
            provider_completion_result.output_tokens,
            provider_completion_result.cached_input_tokens,
        )
        response_json: dict[str, Any] | None = None
        if provider_completion_result.parsed_output is not None:
            response_json = provider_completion_result.parsed_output.model_dump(mode="json")

        call_status = self._resolve_status(provider_completion_result.reason)

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
            llm_call_record.latency_ms = latency_ms
            llm_call_record.provider_request_reference = (
                provider_completion_result.provider_request_reference
            )
            llm_call_record.updated_by_id = auth_user.id
            await db_session.flush()

        logger.info(
            "llm_call_completed",
            llm_type=llm_completion_input.llm_type,
            model_name=tier_settings.model_name,
            purpose=llm_completion_input.purpose,
            input_tokens=provider_completion_result.input_tokens,
            output_tokens=provider_completion_result.output_tokens,
            cached_input_tokens=provider_completion_result.cached_input_tokens,
            reasoning_tokens=provider_completion_result.reasoning_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )

    async def _update_llm_call_failed(
        self,
        llm_call_id: int,
        llm_provider_exception: Exception,
        latency_ms: int,
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
            llm_call_record.status = self._resolve_status(failure_reason)
            llm_call_record.reason = failure_reason
            llm_call_record.error_code = type(llm_provider_exception).__name__
            llm_call_record.error_message = str(llm_provider_exception)
            llm_call_record.latency_ms = latency_ms
            llm_call_record.updated_by_id = auth_user.id
            await db_session.flush()
