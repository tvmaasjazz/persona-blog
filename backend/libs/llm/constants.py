from libs.llm.exceptions import (
    LlmCancelledException,
    LlmContentFilteredException,
    LlmException,
    LlmFailedException,
    LlmNotFinishedException,
    LlmRateLimitedException,
    LlmRefusedException,
    LlmTruncatedException,
    LlmUnavailableException,
)
from libs.llm.types import LlmCallReasonType, LlmCallStatusType

# A call that produced no usable output is INCOMPLETE when the provider answered and FAILED
# when it didn't. Both maps must cover every LlmCallReasonType member.
LLM_STATUS_BY_REASON: dict[LlmCallReasonType, LlmCallStatusType] = {
    LlmCallReasonType.MAX_TOKENS: LlmCallStatusType.INCOMPLETE,
    LlmCallReasonType.CONTENT_FILTER: LlmCallStatusType.INCOMPLETE,
    LlmCallReasonType.REFUSAL: LlmCallStatusType.INCOMPLETE,
    LlmCallReasonType.PROVIDER_ERROR: LlmCallStatusType.FAILED,
    LlmCallReasonType.PROVIDER_UNAVAILABLE: LlmCallStatusType.FAILED,
    LlmCallReasonType.RATE_LIMITED: LlmCallStatusType.FAILED,
    LlmCallReasonType.CANCELLED: LlmCallStatusType.FAILED,
    LlmCallReasonType.NOT_FINISHED: LlmCallStatusType.FAILED,
}

LLM_EXCEPTION_BY_REASON: dict[LlmCallReasonType, type[LlmException]] = {
    LlmCallReasonType.MAX_TOKENS: LlmTruncatedException,
    LlmCallReasonType.CONTENT_FILTER: LlmContentFilteredException,
    LlmCallReasonType.REFUSAL: LlmRefusedException,
    LlmCallReasonType.PROVIDER_ERROR: LlmFailedException,
    LlmCallReasonType.PROVIDER_UNAVAILABLE: LlmUnavailableException,
    LlmCallReasonType.RATE_LIMITED: LlmRateLimitedException,
    LlmCallReasonType.CANCELLED: LlmCancelledException,
    LlmCallReasonType.NOT_FINISHED: LlmNotFinishedException,
}
