from enum import StrEnum


class LlmType(StrEnum):
    """The tier of model a call needs; LlmSettings maps each tier to a model."""

    FAST = "FAST"
    STRONG = "STRONG"
    THINKING = "THINKING"


class LlmProviderType(StrEnum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"


class LlmReasoningEffortType(StrEnum):
    """How hard a reasoning model thinks; each provider maps it to its own values."""

    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LlmCallStatusType(StrEnum):
    """The coarse outcome of a call."""

    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


class LlmCallReasonType(StrEnum):
    """Why a call produced no usable output."""

    MAX_TOKENS = "MAX_TOKENS"
    CONTENT_FILTER = "CONTENT_FILTER"
    REFUSAL = "REFUSAL"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    CANCELLED = "CANCELLED"
    NOT_FINISHED = "NOT_FINISHED"
