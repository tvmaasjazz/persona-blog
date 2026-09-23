from libs.core.exceptions import (
    RateLimitedException,
    ServiceUnavailableException,
    UnprocessableException,
)
from libs.llm.types import LlmCallReasonType


class LlmException(Exception):
    """Every LLM failure carries the reason recorded on its pb_llm_call row."""

    reason: LlmCallReasonType
    message: str

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class LlmTruncatedException(LlmException, UnprocessableException):
    reason = LlmCallReasonType.MAX_TOKENS
    message = "The model ran out of output tokens before finishing"


class LlmContentFilteredException(LlmException, UnprocessableException):
    reason = LlmCallReasonType.CONTENT_FILTER
    message = "The model's response was filtered"


class LlmRefusedException(LlmException, UnprocessableException):
    reason = LlmCallReasonType.REFUSAL
    message = "The model refused to complete this request"


class LlmFailedException(LlmException, ServiceUnavailableException):
    reason = LlmCallReasonType.PROVIDER_ERROR
    message = "The LLM provider could not complete this request"


class LlmUnavailableException(LlmException, ServiceUnavailableException):
    reason = LlmCallReasonType.PROVIDER_UNAVAILABLE
    message = "The LLM provider is unavailable"


class LlmRateLimitedException(LlmException, RateLimitedException):
    reason = LlmCallReasonType.RATE_LIMITED
    message = "The LLM provider rate-limited this request"


class LlmCancelledException(LlmException, ServiceUnavailableException):
    reason = LlmCallReasonType.CANCELLED
    message = "The LLM call was cancelled"


class LlmNotFinishedException(LlmException, ServiceUnavailableException):
    reason = LlmCallReasonType.NOT_FINISHED
    message = "The LLM call did not finish"
