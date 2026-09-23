from uuid import UUID

from pydantic import BaseModel

from apps.api.domains.dev_llm.constants import DEV_LLM_COMPLETE_PURPOSE
from libs.llm.inputs import LlmCompletionInput
from libs.llm.results import LlmCompletionResult
from libs.llm.types import LlmType


class CompleteLlmDto(BaseModel):
    llm_type: LlmType
    system_prompt: str | None
    user_prompt: str

    def to_input(self) -> LlmCompletionInput:
        return LlmCompletionInput(
            llm_type=self.llm_type,
            purpose=DEV_LLM_COMPLETE_PURPOSE,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
        )


class LlmCompletionResponseDto(BaseModel):
    llm_call_identity: UUID
    content: str
    input_tokens: int
    output_tokens: int

    @classmethod
    def from_result(cls, result: LlmCompletionResult) -> LlmCompletionResponseDto:
        return cls(
            llm_call_identity=result.llm_call_identity,
            content=result.content,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
