from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from libs.llm.types import LlmProviderType, LlmType


class LlmTierSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: LlmProviderType
    model_name: str
    max_output_tokens: int
    request_timeout_seconds: int


class LlmModelPricingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_usd_per_million_tokens: Decimal
    cached_input_usd_per_million_tokens: Decimal
    output_usd_per_million_tokens: Decimal


def _default_tiers() -> dict[LlmType, LlmTierSettings]:
    return {
        LlmType.FAST: LlmTierSettings(
            provider=LlmProviderType.OPENAI,
            model_name="gpt-4o-mini",
            max_output_tokens=2048,
            request_timeout_seconds=30,
        ),
        LlmType.STRONG: LlmTierSettings(
            provider=LlmProviderType.OPENAI,
            model_name="gpt-5.6-sol",
            max_output_tokens=4096,
            request_timeout_seconds=60,
        ),
        LlmType.THINKING: LlmTierSettings(
            provider=LlmProviderType.OPENAI,
            model_name="o3",
            max_output_tokens=4096,
            request_timeout_seconds=120,
        ),
    }


def _default_model_pricing() -> dict[str, LlmModelPricingSettings]:
    return {
        "gpt-4o-mini": LlmModelPricingSettings(
            input_usd_per_million_tokens=Decimal("0.15"),
            cached_input_usd_per_million_tokens=Decimal("0.075"),
            output_usd_per_million_tokens=Decimal("0.60"),
        ),
        "gpt-5.6-sol": LlmModelPricingSettings(
            input_usd_per_million_tokens=Decimal("4.00"),
            cached_input_usd_per_million_tokens=Decimal("0.40"),
            output_usd_per_million_tokens=Decimal("20.00"),
        ),
        "o3": LlmModelPricingSettings(
            input_usd_per_million_tokens=Decimal("2.00"),
            cached_input_usd_per_million_tokens=Decimal("0.50"),
            output_usd_per_million_tokens=Decimal("8.00"),
        ),
    }


class LlmSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    tiers: dict[LlmType, LlmTierSettings] = Field(default_factory=_default_tiers)
    model_pricing: dict[str, LlmModelPricingSettings] = Field(
        default_factory=_default_model_pricing
    )
    max_retries: int = 2
