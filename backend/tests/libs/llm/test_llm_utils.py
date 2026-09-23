from decimal import Decimal

import pytest
import structlog.testing

from libs.llm.constants import LLM_EXCEPTION_BY_REASON, LLM_STATUS_BY_REASON
from libs.llm.settings import LlmModelPricingSettings, LlmSettings, LlmTierSettings
from libs.llm.types import LlmCallReasonType, LlmCallStatusType, LlmProviderType, LlmType
from libs.llm.utils import LlmUtils


def test_resolve_status_no_reason_returns_succeeded() -> None:
    call_status = LlmUtils.resolve_status(None)

    assert call_status == LlmCallStatusType.SUCCEEDED


@pytest.mark.parametrize("reason", list(LlmCallReasonType))
def test_resolve_status_every_reason_has_a_status(reason: LlmCallReasonType) -> None:
    call_status = LlmUtils.resolve_status(reason)

    assert call_status == LLM_STATUS_BY_REASON[reason]


@pytest.mark.parametrize("reason", list(LlmCallReasonType))
def test_build_reason_exception_every_reason_has_an_exception(reason: LlmCallReasonType) -> None:
    reason_exception = LlmUtils.build_reason_exception(reason)

    assert isinstance(reason_exception, LLM_EXCEPTION_BY_REASON[reason])
    assert reason_exception.reason == reason


def test_compute_cost_bills_cached_input_tokens_at_the_cached_rate() -> None:
    llm_settings = LlmSettings(
        tiers={
            LlmType.FAST: LlmTierSettings(
                provider=LlmProviderType.OPENAI,
                model_name="test-model",
                max_output_tokens=2048,
                request_timeout_seconds=30,
            )
        },
        model_pricing={
            "test-model": LlmModelPricingSettings(
                input_usd_per_million_tokens=Decimal("2.00"),
                cached_input_usd_per_million_tokens=Decimal("0.50"),
                output_usd_per_million_tokens=Decimal("8.00"),
            )
        },
    )

    cost_usd = LlmUtils.compute_cost(
        llm_settings,
        "test-model",
        input_tokens=1000,
        output_tokens=500,
        cached_input_tokens=200,
    )

    assert cost_usd == Decimal("0.005700")


def test_compute_cost_unpriced_model_returns_none_and_logs_warning() -> None:
    llm_settings = LlmSettings(tiers={}, model_pricing={})

    with structlog.testing.capture_logs() as captured_log_events:
        cost_usd = LlmUtils.compute_cost(
            llm_settings,
            "unpriced-model",
            input_tokens=1000,
            output_tokens=500,
            cached_input_tokens=200,
        )

    llm_pricing_missing_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "llm_pricing_missing"
    ]
    assert cost_usd is None
    assert len(llm_pricing_missing_events) == 1
    assert llm_pricing_missing_events[0]["model_name"] == "unpriced-model"
