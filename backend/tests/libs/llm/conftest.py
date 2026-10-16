from collections.abc import AsyncIterator

import httpx
import pytest
from openai import AsyncOpenAI

from libs.llm.services.openai_llm_service import OpenAiLlmService
from libs.llm.settings import LlmSettings
from tests.stubs.http import HttpHandlerStub


@pytest.fixture
def openai_handler_stub() -> HttpHandlerStub:
    return HttpHandlerStub()


@pytest.fixture
async def openai_llm_service(
    openai_handler_stub: HttpHandlerStub,
) -> AsyncIterator[OpenAiLlmService]:
    openai_transport = httpx.MockTransport(openai_handler_stub.handle)
    async with httpx.AsyncClient(transport=openai_transport) as openai_http_client:
        openai_client = AsyncOpenAI(
            api_key="test-openai-api-key", http_client=openai_http_client, max_retries=0
        )
        llm_settings = LlmSettings(
            max_retries=2, retry_base_delay_seconds=0, retry_max_delay_seconds=0
        )
        yield OpenAiLlmService(openai_client=openai_client, llm_settings=llm_settings)
