import random

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
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
from libs.llm.types import LlmCallReasonType, LlmReasoningEffortType

# OpenAI's spelling of each reasoning effort, for the Responses API's reasoning.effort.
OPENAI_REASONING_EFFORT_BY_TYPE: dict[LlmReasoningEffortType, str] = {
    LlmReasoningEffortType.MINIMAL: "minimal",
    LlmReasoningEffortType.LOW: "low",
    LlmReasoningEffortType.MEDIUM: "medium",
    LlmReasoningEffortType.HIGH: "high",
}


class OpenAiLlmUtils:
    """Builds OpenAI request arguments and maps OpenAI responses and errors to ours."""

    @staticmethod
    def build_instructions_kwargs(provider_input: LlmProviderCompletionInput) -> dict[str, str]:
        """The instructions argument, left out when there is no system prompt."""
        if provider_input.system_prompt is None:
            return {}
        return {"instructions": provider_input.system_prompt}

    @staticmethod
    def build_reasoning_kwargs(
        provider_input: LlmProviderCompletionInput,
    ) -> dict[str, dict[str, str]]:
        """The reasoning argument, left out when no effort is set."""
        if provider_input.reasoning_effort is None:
            return {}
        openai_reasoning_effort = OPENAI_REASONING_EFFORT_BY_TYPE.get(
            provider_input.reasoning_effort
        )
        if openai_reasoning_effort is None:
            raise NotImplementedError(
                f"No OpenAI reasoning effort for {provider_input.reasoning_effort}"
            )
        return {"reasoning": {"effort": openai_reasoning_effort}}

    @staticmethod
    def is_retryable_error(openai_error: OpenAIError) -> bool:
        """True for rate limits, server errors and dropped connections, but not timeouts."""
        # APITimeoutError subclasses APIConnectionError, so it is ruled out first.
        if isinstance(openai_error, APITimeoutError):
            return False
        return isinstance(openai_error, RateLimitError | InternalServerError | APIConnectionError)

    @staticmethod
    def compute_retry_delay_seconds(
        attempt: int, base_delay_seconds: float, max_delay_seconds: float
    ) -> float:
        """A random wait up to the exponentially growing, capped delay (full jitter)."""
        return random.uniform(0, min(max_delay_seconds, base_delay_seconds * 2**attempt))

    @staticmethod
    def build_provider_completion_result(
        response: Response,
        provider_request_reference: str | None,
        parsed_output: BaseModel | None,
    ) -> LlmProviderCompletionResult:
        """Maps a response to our result, counting a missing usage as zero tokens and
        using the refusal text as content when the model refused."""
        reason, refusal_text = OpenAiLlmUtils.resolve_reason(response)
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
    def resolve_reason(response: Response) -> tuple[LlmCallReasonType | None, str | None]:
        """Returns the failure reason (None for usable output) and any refusal text."""
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

        # queued, in_progress and unmapped incomplete reasons: the call never reached a usable end
        return LlmCallReasonType.NOT_FINISHED, None

    @staticmethod
    def map_openai_error(openai_error: OpenAIError) -> Exception:
        """The LlmException for an OpenAI error, carrying its message as provider_message."""
        provider_message = str(openai_error)
        if isinstance(openai_error, RateLimitError):
            return LlmRateLimitedException(provider_message=provider_message)
        if isinstance(
            openai_error,
            APITimeoutError | APIConnectionError | AuthenticationError | PermissionDeniedError,
        ):
            # We couldn't reach or use the provider at all.
            return LlmUnavailableException(provider_message=provider_message)
        if isinstance(openai_error, InternalServerError | APIStatusError):
            # The provider answered, with an error of its own.
            return LlmFailedException(provider_message=provider_message)
        return LlmFailedException(provider_message=provider_message)
