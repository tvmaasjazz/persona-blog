import pytest
from fastapi import FastAPI

from apps.api.core.dependencies import get_llm_service
from tests.stubs.llm import LlmServiceStub


@pytest.fixture(autouse=True)
def llm_service_stub(fastapi_app: FastAPI) -> LlmServiceStub:
    llm_service_stub = LlmServiceStub()
    fastapi_app.dependency_overrides[get_llm_service] = lambda: llm_service_stub
    return llm_service_stub
