import asyncio
from typing import Any

from pydantic import BaseModel

from libs.auth.results import AuthUser
from libs.llm.inputs import LlmCompletionInput, LlmProviderCompletionInput
from libs.llm.results import (
    LlmCompletionResult,
    LlmProviderCompletionResult,
    LlmStructuredCompletionResult,
)
from libs.llm.services.base_llm_provider_service import BaseLlmProviderService
from libs.llm.services.llm_service import LlmService
from tests.factories.llm import build_llm_completion_result, build_llm_provider_completion_result


class LlmProviderServiceStub(BaseLlmProviderService):
    def __init__(self) -> None:
        self.complete_inputs: list[LlmProviderCompletionInput] = []
        self.complete_result = build_llm_provider_completion_result()
        self.complete_error: Exception | None = None
        self.complete_structured_inputs: list[LlmProviderCompletionInput] = []
        self.complete_structured_result = build_llm_provider_completion_result()
        self.complete_structured_error: Exception | None = None

    async def complete(
        self, provider_input: LlmProviderCompletionInput
    ) -> LlmProviderCompletionResult:
        self.complete_inputs.append(provider_input)
        if self.complete_error is not None:
            raise self.complete_error
        return self.complete_result

    async def complete_structured(
        self, provider_input: LlmProviderCompletionInput, output_type: type[BaseModel]
    ) -> LlmProviderCompletionResult:
        self.complete_structured_inputs.append(provider_input)
        if self.complete_structured_error is not None:
            raise self.complete_structured_error
        return self.complete_structured_result


class LlmServiceStub(LlmService):
    def __init__(self) -> None:
        self.complete_inputs: list[LlmCompletionInput] = []
        self.complete_result = build_llm_completion_result()
        self.complete_results: list[LlmCompletionResult] | None = None
        self.complete_error: Exception | None = None
        self.complete_is_blocked = False
        self.complete_started_event = asyncio.Event()
        self.complete_unblock_event = asyncio.Event()
        self.complete_structured_inputs: list[LlmCompletionInput] = []
        self.complete_structured_result: LlmStructuredCompletionResult[Any] | None = None
        self.complete_structured_error: Exception | None = None

    async def complete(
        self, llm_completion_input: LlmCompletionInput, auth_user: AuthUser
    ) -> LlmCompletionResult:
        self.complete_inputs.append(llm_completion_input)
        self.complete_started_event.set()
        if self.complete_is_blocked:
            await self.complete_unblock_event.wait()
        if self.complete_error is not None:
            raise self.complete_error
        if self.complete_results is not None:
            return self.complete_results.pop(0)
        return self.complete_result

    async def complete_structured[T: BaseModel](
        self,
        llm_completion_input: LlmCompletionInput,
        output_type: type[T],
        auth_user: AuthUser,
    ) -> LlmStructuredCompletionResult[T]:
        self.complete_structured_inputs.append(llm_completion_input)
        if self.complete_structured_error is not None:
            raise self.complete_structured_error
        assert self.complete_structured_result is not None
        return self.complete_structured_result
