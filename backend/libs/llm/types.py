from enum import StrEnum


class LlmType(StrEnum):
    """What a call needs, not which model runs it. LlmSettings maps each tier to a model."""

    FAST = "FAST"
    STRONG = "STRONG"
    THINKING = "THINKING"


class LlmProviderType(StrEnum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"


class LlmCallStatusType(StrEnum):
    """The coarse outcome of a call. LlmCallReasonType carries the detail."""

    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


class LlmCallReasonType(StrEnum):
    """Why a call produced no usable output. Null on a call that succeeded."""

    MAX_TOKENS = "MAX_TOKENS"
    CONTENT_FILTER = "CONTENT_FILTER"
    REFUSAL = "REFUSAL"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    CANCELLED = "CANCELLED"
    NOT_FINISHED = "NOT_FINISHED"
