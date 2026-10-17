import os

import pytest
from openai import AsyncOpenAI
from pydantic import BaseModel

from libs.llm.services.openai_llm_service import OpenAiLlmService
from libs.llm.settings import LlmSettings
from tests.factories.llm import build_llm_provider_completion_input


class _SampleOutput(BaseModel):
    answer: str


@pytest.mark.live_llm
async def test_complete_returns_non_empty_content_and_positive_token_counts() -> None:
    live_openai_api_key = os.environ.get("LIVE_OPENAI_API_KEY")
    if live_openai_api_key is None:
        pytest.skip("LIVE_OPENAI_API_KEY is not set")

    openai_client = AsyncOpenAI(api_key=live_openai_api_key, max_retries=0)
    openai_llm_service = OpenAiLlmService(
        openai_client=openai_client, llm_settings=LlmSettings(max_retries=2)
    )
    provider_input = build_llm_provider_completion_input(
        model_name="gpt-4o-mini", user_prompt="Reply with a short greeting."
    )

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.content != ""
    assert complete_result.input_tokens > 0
    assert complete_result.output_tokens > 0


@pytest.mark.live_llm
async def test_complete_structured_returns_positive_token_counts() -> None:
    live_openai_api_key = os.environ.get("LIVE_OPENAI_API_KEY")
    if live_openai_api_key is None:
        pytest.skip("LIVE_OPENAI_API_KEY is not set")

    openai_client = AsyncOpenAI(api_key=live_openai_api_key, max_retries=0)
    openai_llm_service = OpenAiLlmService(
        openai_client=openai_client, llm_settings=LlmSettings(max_retries=2)
    )
    provider_input = build_llm_provider_completion_input(
        model_name="gpt-4o-mini", user_prompt="Answer with a single word."
    )

    complete_structured_result = await openai_llm_service.complete_structured(
        provider_input, _SampleOutput
    )

    assert isinstance(complete_structured_result.parsed_output, _SampleOutput)
    assert complete_structured_result.parsed_output.answer != ""
    assert complete_structured_result.input_tokens > 0
    assert complete_structured_result.output_tokens > 0
