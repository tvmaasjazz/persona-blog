from decimal import Decimal

import pytest

from libs.llm.constants import LLM_EXCEPTION_BY_REASON, LLM_STATUS_BY_REASON
from libs.llm.settings import FastLlmTierSettings, LlmSettings
from libs.llm.types import LlmCallReasonType, LlmCallStatusType, LlmProviderType
from libs.llm.utils import LlmUtils
from tests.factories.llm import build_llm_model_pricing_by_model_name


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
        fast=FastLlmTierSettings(
            provider=LlmProviderType.OPENAI,
            model_name="test-model",
            max_output_tokens=2048,
            request_timeout_seconds=30,
        ),
        model_pricing=build_llm_model_pricing_by_model_name(extra_model_names=["test-model"]),
    )

    cost_usd = LlmUtils.compute_cost(
        llm_settings,
        "test-model",
        input_tokens=1000,
        output_tokens=500,
        cached_input_tokens=200,
    )

    assert cost_usd == Decimal("0.005700")
