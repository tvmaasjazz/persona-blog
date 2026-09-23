from collections.abc import AsyncIterator

import httpx2
import pytest
from openai import AsyncOpenAI

from libs.openai_llm.services import OpenAiLlmService
from tests.stubs.http2 import Httpx2HandlerStub


@pytest.fixture
def openai_handler_stub() -> Httpx2HandlerStub:
    return Httpx2HandlerStub()


@pytest.fixture
async def openai_llm_service(
    openai_handler_stub: Httpx2HandlerStub,
) -> AsyncIterator[OpenAiLlmService]:
    openai_transport = httpx2.MockTransport(openai_handler_stub.handle)
    async with httpx2.AsyncClient(transport=openai_transport) as openai_http_client:
        openai_client = AsyncOpenAI(
            api_key="test-openai-api-key", http_client=openai_http_client, max_retries=0
        )
        yield OpenAiLlmService(openai_client=openai_client)
