import structlog
from pydantic import BaseModel

from libs.auth.results import AuthUser
from libs.core.utils.date_time_utils import DateTimeUtils
from libs.llm.exceptions import LlmUnavailableException
from libs.llm.inputs import LlmCompletionInput, LlmProviderCompletionInput
from libs.llm.results import (
    CompleteLlmCallResult,
    LlmCompletionResult,
    LlmStructuredCompletionResult,
)
from libs.llm.services.base_llm_provider_service import BaseLlmProviderService
from libs.llm.services.llm_call_service import LlmCallService
from libs.llm.settings import LlmSettings, LlmTierSettings
from libs.llm.types import LlmProviderType, LlmType
from libs.llm.utils import LlmUtils

logger = structlog.get_logger(__name__)


class LlmService:
    def __init__(
        self,
        llm_provider_services: dict[LlmProviderType, BaseLlmProviderService],
        llm_call_service: LlmCallService,
        llm_settings: LlmSettings,
    ) -> None:
        self._llm_provider_services = llm_provider_services
        self._llm_call_service = llm_call_service
        self._llm_settings = llm_settings

    async def complete(
        self, llm_completion_input: LlmCompletionInput, auth_user: AuthUser
    ) -> LlmCompletionResult:
        complete_llm_call_result = await self._complete(
            llm_completion_input, auth_user, output_type=None
        )
        provider_completion_result = complete_llm_call_result.provider_completion_result
        return LlmCompletionResult(
            llm_call_identity=complete_llm_call_result.llm_call_identity,
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
        complete_llm_call_result = await self._complete(
            llm_completion_input, auth_user, output_type=output_type
        )
        provider_completion_result = complete_llm_call_result.provider_completion_result
        if provider_completion_result.parsed_output is None:
            raise LlmUnavailableException("The model returned no structured output")

        return LlmStructuredCompletionResult[T](
            llm_call_identity=complete_llm_call_result.llm_call_identity,
            output=provider_completion_result.parsed_output,
            input_tokens=provider_completion_result.input_tokens,
            output_tokens=provider_completion_result.output_tokens,
        )

    async def _complete(
        self,
        llm_completion_input: LlmCompletionInput,
        auth_user: AuthUser,
        output_type: type[BaseModel] | None,
    ) -> CompleteLlmCallResult:
        tier_settings = self._resolve_tier(llm_completion_input.llm_type)
        llm_provider_service = self._resolve_provider_service(tier_settings.provider)

        create_pending_llm_call_result = await self._llm_call_service.create_pending_llm_call(
            llm_completion_input, tier_settings, auth_user
        )
        llm_call_id = create_pending_llm_call_result.llm_call_id
        llm_call_identity = create_pending_llm_call_result.llm_call_identity

        provider_input = LlmProviderCompletionInput(
            model_name=tier_settings.model_name,
            system_prompt=llm_completion_input.system_prompt,
            user_prompt=llm_completion_input.user_prompt,
            max_output_tokens=tier_settings.max_output_tokens,
            request_timeout_seconds=tier_settings.request_timeout_seconds,
        )

        start_time = DateTimeUtils.now_monotonic()
        try:
            if output_type is None:
                provider_completion_result = await llm_provider_service.complete(provider_input)
            else:
                provider_completion_result = await llm_provider_service.complete_structured(
                    provider_input, output_type
                )
        except Exception as llm_provider_exception:
            duration_ms = DateTimeUtils.elapsed_ms(start_time)
            await self._llm_call_service.fail_llm_call(
                llm_call_id, llm_provider_exception, duration_ms, auth_user
            )
            raise
        duration_ms = DateTimeUtils.elapsed_ms(start_time)

        cost_usd = LlmUtils.compute_cost(
            self._llm_settings,
            tier_settings.model_name,
            provider_completion_result.input_tokens,
            provider_completion_result.output_tokens,
            provider_completion_result.cached_input_tokens,
        )

        # The row is written first, so a call that produced no usable output is still on
        # record with its tokens and cost before the exception leaves this method.
        await self._llm_call_service.complete_llm_call(
            llm_call_id, provider_completion_result, cost_usd, duration_ms, auth_user
        )

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
            duration_ms=duration_ms,
        )

        if provider_completion_result.reason is not None:
            raise LlmUtils.build_reason_exception(provider_completion_result.reason)

        return CompleteLlmCallResult(
            llm_call_identity=llm_call_identity,
            provider_completion_result=provider_completion_result,
        )

    def _resolve_tier(self, llm_type: LlmType) -> LlmTierSettings:
        tier_settings = self._llm_settings.tiers.get(llm_type)
        if tier_settings is None:
            raise NotImplementedError(f"No tier configured for {llm_type}")
        return tier_settings

    def _resolve_provider_service(self, provider: LlmProviderType) -> BaseLlmProviderService:
        llm_provider_service = self._llm_provider_services.get(provider)
        if llm_provider_service is None:
            raise NotImplementedError(f"No provider service registered for {provider}")
        return llm_provider_service
