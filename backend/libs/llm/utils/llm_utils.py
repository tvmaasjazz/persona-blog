from decimal import Decimal

import structlog

from libs.llm.constants import LLM_EXCEPTION_BY_REASON, LLM_STATUS_BY_REASON
from libs.llm.exceptions import LlmException
from libs.llm.settings import LlmSettings
from libs.llm.types import LlmCallReasonType, LlmCallStatusType

logger = structlog.get_logger(__name__)


class LlmUtils:
    """Maps a call's failure reason to its status and exception, and prices its tokens."""

    @staticmethod
    def resolve_status(reason: LlmCallReasonType | None) -> LlmCallStatusType:
        """Maps a call's failure reason to its status, SUCCEEDED when there is none."""
        if reason is None:
            return LlmCallStatusType.SUCCEEDED
        call_status = LLM_STATUS_BY_REASON.get(reason)
        if call_status is None:
            raise NotImplementedError(f"No status registered for {reason}")
        return call_status

    @staticmethod
    def build_reason_exception(reason: LlmCallReasonType) -> LlmException:
        """The exception to raise for a reason; NotImplementedError for one with none."""
        exception_class = LLM_EXCEPTION_BY_REASON.get(reason)
        if exception_class is None:
            raise NotImplementedError(f"No exception registered for {reason}")
        return exception_class()

    @staticmethod
    def compute_cost(
        llm_settings: LlmSettings,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int,
    ) -> Decimal | None:
        """The call's cost in USD, or None for an unpriced model, since 0 would read as free."""
        model_pricing = llm_settings.model_pricing.get(model_name)
        if model_pricing is None:
            logger.warning("llm_pricing_missing", model_name=model_name)
            return None

        billed_input_tokens = input_tokens - cached_input_tokens
        million_tokens = Decimal(1_000_000)
        return (
            billed_input_tokens * model_pricing.input_usd_per_million_tokens
            + cached_input_tokens * model_pricing.cached_input_usd_per_million_tokens
            + output_tokens * model_pricing.output_usd_per_million_tokens
        ) / million_tokens
