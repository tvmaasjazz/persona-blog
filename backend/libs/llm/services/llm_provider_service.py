from abc import ABC, abstractmethod

from pydantic import BaseModel

from libs.llm.inputs import LlmProviderCompletionInput
from libs.llm.results import LlmProviderCompletionResult


class LlmProviderService(ABC):
    @abstractmethod
    async def complete(
        self, provider_input: LlmProviderCompletionInput
    ) -> LlmProviderCompletionResult: ...

    @abstractmethod
    async def complete_structured(
        self, provider_input: LlmProviderCompletionInput, output_type: type[BaseModel]
    ) -> LlmProviderCompletionResult: ...
