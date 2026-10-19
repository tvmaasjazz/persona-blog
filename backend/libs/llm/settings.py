from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from libs.llm.types import LlmProviderType, LlmReasoningEffortType


class LlmTierSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: LlmProviderType
    model_name: str
    max_output_tokens: int
    request_timeout_seconds: int
    reasoning_effort: LlmReasoningEffortType | None = None


# One class per tier, so one value can be overridden alone (LLM__STRONG__MODEL_NAME)
class FastLlmTierSettings(LlmTierSettings):
    provider: LlmProviderType = LlmProviderType.OPENAI
    model_name: str = "gpt-5.4-nano"
    max_output_tokens: int = 8192
    request_timeout_seconds: int = 30
    reasoning_effort: LlmReasoningEffortType | None = LlmReasoningEffortType.LOW


class StrongLlmTierSettings(LlmTierSettings):
    provider: LlmProviderType = LlmProviderType.OPENAI
    model_name: str = "gpt-5.6-sol"
    max_output_tokens: int = 4096
    request_timeout_seconds: int = 120


class ThinkingLlmTierSettings(LlmTierSettings):
    provider: LlmProviderType = LlmProviderType.OPENAI
    model_name: str = "o3"
    max_output_tokens: int = 4096
    request_timeout_seconds: int = 120


class LlmModelPricingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_usd_per_million_tokens: Decimal
    cached_input_usd_per_million_tokens: Decimal
    output_usd_per_million_tokens: Decimal


def _default_model_pricing() -> dict[str, LlmModelPricingSettings]:
    return {
        "gpt-4o-mini": LlmModelPricingSettings(
            input_usd_per_million_tokens=Decimal("0.15"),
            cached_input_usd_per_million_tokens=Decimal("0.075"),
            output_usd_per_million_tokens=Decimal("0.60"),
        ),
        "gpt-5.4-nano": LlmModelPricingSettings(
            input_usd_per_million_tokens=Decimal("0.20"),
            cached_input_usd_per_million_tokens=Decimal("0.02"),
            output_usd_per_million_tokens=Decimal("1.25"),
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

    fast: FastLlmTierSettings = Field(default_factory=FastLlmTierSettings)
    strong: StrongLlmTierSettings = Field(default_factory=StrongLlmTierSettings)
    thinking: ThinkingLlmTierSettings = Field(default_factory=ThinkingLlmTierSettings)
    model_pricing: dict[str, LlmModelPricingSettings] = Field(
        default_factory=_default_model_pricing
    )
    max_retries: int = 2
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 20.0
