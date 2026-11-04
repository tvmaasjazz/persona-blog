from decimal import Decimal

import pytest
from pydantic import ValidationError

from libs.llm.settings import (
    FastLlmTierSettings,
    LlmModelPricingSettings,
    LlmSettings,
    LlmTierSettings,
    StrongLlmTierSettings,
    ThinkingLlmTierSettings,
)


def test_llm_settings_every_tier_model_priced_is_accepted() -> None:
    llm_settings = LlmSettings(
        fast=FastLlmTierSettings(model_name="priced-fast-model"),
        strong=StrongLlmTierSettings(model_name="priced-strong-model"),
        thinking=ThinkingLlmTierSettings(model_name="priced-thinking-model"),
        model_pricing={
            model_name: LlmModelPricingSettings(
                input_usd_per_million_tokens=Decimal("1.00"),
                cached_input_usd_per_million_tokens=Decimal("0.10"),
                output_usd_per_million_tokens=Decimal("4.00"),
            )
            for model_name in [
                "priced-fast-model",
                "priced-strong-model",
                "priced-thinking-model",
            ]
        },
    )

    assert llm_settings.fast.model_name == "priced-fast-model"


@pytest.mark.parametrize(
    "unpriced_tier_settings",
    [
        pytest.param({"fast": FastLlmTierSettings(model_name="unpriced-model")}, id="fast"),
        pytest.param({"strong": StrongLlmTierSettings(model_name="unpriced-model")}, id="strong"),
        pytest.param(
            {"thinking": ThinkingLlmTierSettings(model_name="unpriced-model")}, id="thinking"
        ),
    ],
)
def test_llm_settings_tier_model_without_pricing_raises_validation_error(
    unpriced_tier_settings: dict[str, LlmTierSettings],
) -> None:
    with pytest.raises(ValidationError):
        LlmSettings(**unpriced_tier_settings)
