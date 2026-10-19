import asyncio
from collections.abc import Awaitable, Callable

import structlog
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel

from libs.llm.inputs import LlmProviderCompletionInput
from libs.llm.results import LlmProviderCompletionResult
from libs.llm.services.base_llm_provider_service import BaseLlmProviderService
from libs.llm.settings import LlmSettings
from libs.llm.utils import OpenAiLlmUtils

logger = structlog.get_logger(__name__)


class OpenAiLlmService(BaseLlmProviderService):
    """Runs completions on OpenAI's Responses API, retrying errors worth retrying."""

    def __init__(self, openai_client: AsyncOpenAI, llm_settings: LlmSettings) -> None:
        self._openai_client = openai_client
        self._llm_settings = llm_settings

    async def complete(
        self, provider_input: LlmProviderCompletionInput
    ) -> LlmProviderCompletionResult:
        """Runs a free-text completion; OpenAI errors surface as mapped LlmExceptions."""
        raw_response = await self._send_with_retries(
            lambda: self._openai_client.responses.with_raw_response.create(
                model=provider_input.model_name,
                **OpenAiLlmUtils.build_instructions_kwargs(provider_input),
                **OpenAiLlmUtils.build_reasoning_kwargs(provider_input),
                input=provider_input.user_prompt,
                max_output_tokens=provider_input.max_output_tokens,
                timeout=provider_input.request_timeout_seconds,
            )
        )

        response = raw_response.parse()
        return OpenAiLlmUtils.build_provider_completion_result(
            response, raw_response.request_id, None
        )

    async def complete_structured(
        self, provider_input: LlmProviderCompletionInput, output_type: type[BaseModel]
    ) -> LlmProviderCompletionResult:
        """Runs a completion OpenAI parses into output_type, set on the result's parsed_output."""
        raw_response = await self._send_with_retries(
            lambda: self._openai_client.responses.with_raw_response.parse(
                model=provider_input.model_name,
                **OpenAiLlmUtils.build_instructions_kwargs(provider_input),
                **OpenAiLlmUtils.build_reasoning_kwargs(provider_input),
                input=provider_input.user_prompt,
                max_output_tokens=provider_input.max_output_tokens,
                timeout=provider_input.request_timeout_seconds,
                text_format=output_type,
            )
        )

        response = raw_response.parse()
        return OpenAiLlmUtils.build_provider_completion_result(
            response, raw_response.request_id, response.output_parsed
        )

    # The client is built with max_retries=0, so every retry happens here.
    async def _send_with_retries[T](self, send_request: Callable[[], Awaitable[T]]) -> T:
        attempt = 0
        while True:
            try:
                return await send_request()
            except OpenAIError as openai_error:
                is_out_of_retries = attempt >= self._llm_settings.max_retries
                if is_out_of_retries or not OpenAiLlmUtils.is_retryable_error(openai_error):
                    raise OpenAiLlmUtils.map_openai_error(openai_error) from openai_error

                delay_seconds = OpenAiLlmUtils.compute_retry_delay_seconds(
                    attempt,
                    self._llm_settings.retry_base_delay_seconds,
                    self._llm_settings.retry_max_delay_seconds,
                )
                logger.warning(
                    "llm_provider_retry",
                    attempt=attempt + 1,
                    error_type=type(openai_error).__name__,
                    provider_request_reference=getattr(openai_error, "request_id", None),
                    delay_seconds=delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
                attempt += 1
