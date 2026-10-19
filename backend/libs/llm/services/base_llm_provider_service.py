from abc import ABC, abstractmethod

from pydantic import BaseModel

from libs.llm.inputs import LlmProviderCompletionInput
from libs.llm.results import LlmProviderCompletionResult


class BaseLlmProviderService(ABC):
    """The contract every LLM provider implements to run a completion."""

    @abstractmethod
    async def complete(
        self, provider_input: LlmProviderCompletionInput
    ) -> LlmProviderCompletionResult:
        """Runs a free-text completion; raises an LlmException when the provider fails."""
        ...

    @abstractmethod
    async def complete_structured(
        self, provider_input: LlmProviderCompletionInput, output_type: type[BaseModel]
    ) -> LlmProviderCompletionResult:
        """Runs a completion parsed into output_type, left on the result's parsed_output."""
        ...
