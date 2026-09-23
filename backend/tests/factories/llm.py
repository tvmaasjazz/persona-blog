from uuid import uuid4

from pydantic import BaseModel

from libs.llm.inputs import LlmCompletionInput, LlmProviderCompletionInput
from libs.llm.results import LlmCompletionResult, LlmProviderCompletionResult
from libs.llm.types import LlmCallReasonType, LlmType


def build_llm_completion_input(
    *,
    llm_type: LlmType = LlmType.FAST,
    purpose: str = "test_purpose",
    system_prompt: str | None = "You are a helpful assistant.",
    user_prompt: str = "Say hello.",
) -> LlmCompletionInput:
    return LlmCompletionInput(
        llm_type=llm_type,
        purpose=purpose,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def build_llm_provider_completion_input(
    *,
    model_name: str = "test-model",
    system_prompt: str | None = "You are a helpful assistant.",
    user_prompt: str = "Say hello.",
    max_output_tokens: int = 2048,
    request_timeout_seconds: int = 30,
) -> LlmProviderCompletionInput:
    return LlmProviderCompletionInput(
        model_name=model_name,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_output_tokens=max_output_tokens,
        request_timeout_seconds=request_timeout_seconds,
    )


def build_llm_completion_result(
    *,
    content: str = "Hello there.",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> LlmCompletionResult:
    return LlmCompletionResult(
        llm_call_identity=uuid4(),
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def build_llm_provider_completion_result(
    *,
    content: str = "Hello there.",
    parsed_output: BaseModel | None = None,
    reason: LlmCallReasonType | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cached_input_tokens: int = 0,
    reasoning_tokens: int = 0,
    provider_request_reference: str | None = "req_stub",
) -> LlmProviderCompletionResult:
    return LlmProviderCompletionResult(
        content=content,
        parsed_output=parsed_output,
        reason=reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        reasoning_tokens=reasoning_tokens,
        provider_request_reference=provider_request_reference,
    )
