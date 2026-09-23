from typing import Any


def build_openai_responses_payload(
    *,
    response_id: str = "resp_stub",
    model: str = "test-model",
    status: str = "completed",
    output_text: str = "Hello there.",
    refusal_text: str | None = None,
    incomplete_reason: str | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cached_tokens: int = 0,
    reasoning_tokens: int = 0,
    include_usage: bool = True,
) -> dict[str, Any]:
    if refusal_text is not None:
        output_content = [{"type": "refusal", "refusal": refusal_text}]
    else:
        output_content = [{"type": "output_text", "text": output_text, "annotations": []}]

    responses_payload: dict[str, Any] = {
        "id": response_id,
        "object": "response",
        "created_at": 1700000000,
        "status": status,
        "model": model,
        "output": [
            {
                "id": "msg_stub",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": output_content,
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
    }
    if incomplete_reason is not None:
        responses_payload["incomplete_details"] = {"reason": incomplete_reason}
    if include_usage:
        responses_payload["usage"] = {
            "input_tokens": input_tokens,
            "input_tokens_details": {"cached_tokens": cached_tokens, "cache_write_tokens": 0},
            "output_tokens": output_tokens,
            "output_tokens_details": {"reasoning_tokens": reasoning_tokens},
            "total_tokens": input_tokens + output_tokens,
        }
    return responses_payload


def build_openai_error_payload(*, message: str = "stub provider error") -> dict[str, Any]:
    return {"error": {"message": message, "type": "stub_error"}}
