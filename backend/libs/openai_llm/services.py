from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    InternalServerError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.responses import Response
from pydantic import BaseModel

from libs.llm.exceptions import (
    LlmFailedException,
    LlmRateLimitedException,
    LlmUnavailableException,
)
from libs.llm.inputs import LlmProviderCompletionInput
from libs.llm.results import LlmProviderCompletionResult
from libs.llm.services.llm_provider_service import LlmProviderService
from libs.llm.types import LlmCallReasonType


class OpenAiLlmService(LlmProviderService):
    def __init__(self, openai_client: AsyncOpenAI | None) -> None:
        self._openai_client = openai_client

    async def complete(
        self, provider_input: LlmProviderCompletionInput
    ) -> LlmProviderCompletionResult:
        if self._openai_client is None:
            raise LlmUnavailableException("No OpenAI API key is configured")

        try:
            raw_response = await self._openai_client.responses.with_raw_response.create(
                model=provider_input.model_name,
                **self._build_instructions_kwargs(provider_input),
                input=provider_input.user_prompt,
                max_output_tokens=provider_input.max_output_tokens,
                timeout=provider_input.request_timeout_seconds,
            )
        except OpenAIError as openai_error:
            raise self._map_openai_error(openai_error) from openai_error

        response = raw_response.parse()
        return self._build_provider_completion_result(response, raw_response.request_id, None)

    async def complete_structured(
        self, provider_input: LlmProviderCompletionInput, output_type: type[BaseModel]
    ) -> LlmProviderCompletionResult:
        if self._openai_client is None:
            raise LlmUnavailableException("No OpenAI API key is configured")

        try:
            raw_response = await self._openai_client.responses.with_raw_response.parse(
                model=provider_input.model_name,
                **self._build_instructions_kwargs(provider_input),
                input=provider_input.user_prompt,
                max_output_tokens=provider_input.max_output_tokens,
                timeout=provider_input.request_timeout_seconds,
                text_format=output_type,
            )
        except OpenAIError as openai_error:
            raise self._map_openai_error(openai_error) from openai_error

        response = raw_response.parse()
        return self._build_provider_completion_result(
            response, raw_response.request_id, response.output_parsed
        )

    @staticmethod
    def _build_instructions_kwargs(provider_input: LlmProviderCompletionInput) -> dict[str, str]:
        if provider_input.system_prompt is None:
            return {}
        return {"instructions": provider_input.system_prompt}

    def _build_provider_completion_result(
        self,
        response: Response,
        provider_request_reference: str | None,
        parsed_output: BaseModel | None,
    ) -> LlmProviderCompletionResult:
        reason, refusal_text = self._resolve_reason(response)
        usage = response.usage
        input_tokens = usage.input_tokens if usage is not None else 0
        output_tokens = usage.output_tokens if usage is not None else 0
        cached_input_tokens = (
            usage.input_tokens_details.cached_tokens
            if usage is not None and usage.input_tokens_details is not None
            else 0
        )
        reasoning_tokens = (
            usage.output_tokens_details.reasoning_tokens
            if usage is not None and usage.output_tokens_details is not None
            else 0
        )

        return LlmProviderCompletionResult(
            content=refusal_text if refusal_text is not None else response.output_text,
            parsed_output=parsed_output,
            reason=reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            reasoning_tokens=reasoning_tokens,
            provider_request_reference=provider_request_reference,
        )

    @staticmethod
    def _resolve_reason(response: Response) -> tuple[LlmCallReasonType | None, str | None]:
        """A reason of None means the call produced usable output. The second value is the
        refusal text, which the provider returns in place of content."""
        for output_item in response.output:
            for content_item in getattr(output_item, "content", []) or []:
                if content_item.type == "refusal":
                    return LlmCallReasonType.REFUSAL, content_item.refusal

        if response.status == "completed":
            return None, None
        if response.status == "failed":
            return LlmCallReasonType.PROVIDER_ERROR, None
        if response.status == "cancelled":
            return LlmCallReasonType.CANCELLED, None

        if response.status == "incomplete" and response.incomplete_details is not None:
            incomplete_reason = response.incomplete_details.reason
            if incomplete_reason == "max_output_tokens":
                return LlmCallReasonType.MAX_TOKENS, None
            if incomplete_reason == "content_filter":
                return LlmCallReasonType.CONTENT_FILTER, None

        # queued, in_progress, and the incomplete reasons we don't map yet: the call never
        # reached a usable end, so it is recorded as unfinished rather than as a clean stop.
        return LlmCallReasonType.NOT_FINISHED, None

    @staticmethod
    def _map_openai_error(openai_error: OpenAIError) -> Exception:
        if isinstance(openai_error, RateLimitError):
            return LlmRateLimitedException()
        if isinstance(
            openai_error,
            APITimeoutError | APIConnectionError | AuthenticationError | PermissionDeniedError,
        ):
            # We couldn't reach or use the provider at all.
            return LlmUnavailableException()
        if isinstance(openai_error, InternalServerError | APIStatusError):
            # The provider answered, with an error of its own.
            return LlmFailedException()
        return LlmFailedException()
