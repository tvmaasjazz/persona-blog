from uuid import UUID

from pydantic import BaseModel

from libs.llm.types import LlmCallReasonType


class LlmCompletionResult(BaseModel):
    llm_call_identity: UUID
    content: str
    input_tokens: int
    output_tokens: int


class LlmStructuredCompletionResult[T: BaseModel](BaseModel):
    llm_call_identity: UUID
    output: T
    input_tokens: int
    output_tokens: int


class LlmProviderCompletionResult(BaseModel):
    content: str
    parsed_output: BaseModel | None
    reason: LlmCallReasonType | None
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    provider_request_reference: str | None
