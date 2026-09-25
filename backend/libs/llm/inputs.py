from pydantic import BaseModel

from libs.llm.types import LlmType


class LlmCompletionInput(BaseModel):
    llm_type: LlmType
    purpose: str
    system_prompt: str | None
    user_prompt: str
    run_id: int | None = None
    step_id: int | None = None


class LlmProviderCompletionInput(BaseModel):
    model_name: str
    system_prompt: str | None
    user_prompt: str
    max_output_tokens: int
    request_timeout_seconds: int
