import json
from typing import Any

import httpx
import pytest
import structlog.testing
from pydantic import BaseModel

from libs.llm.exceptions import (
    LlmFailedException,
    LlmRateLimitedException,
    LlmUnavailableException,
)
from libs.llm.results import LlmProviderCompletionResult
from libs.llm.services.openai_llm_service import OpenAiLlmService
from libs.llm.types import LlmCallReasonType, LlmReasoningEffortType
from tests.factories.llm import build_llm_provider_completion_input
from tests.payloads.openai import build_openai_error_payload, build_openai_responses_payload
from tests.stubs.http import HttpHandlerStub


class _SampleOutput(BaseModel):
    answer: str


async def test_complete_returns_content_and_token_counts(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        response_id="resp_abc123",
        output_text="Hello there.",
        input_tokens=120,
        output_tokens=40,
        cached_tokens=20,
        reasoning_tokens=5,
    )
    openai_handler_stub.handle_responses.append(
        httpx.Response(200, json=openai_responses_payload, headers={"x-request-id": "req-abc123"})
    )
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result == LlmProviderCompletionResult(
        content="Hello there.",
        parsed_output=None,
        reason=None,
        input_tokens=120,
        output_tokens=40,
        cached_input_tokens=20,
        reasoning_tokens=5,
        provider_request_reference="req-abc123",
    )


@pytest.mark.parametrize(
    ("status", "incomplete_reason", "expected_reason"),
    [
        pytest.param("completed", None, None, id="succeeded"),
        pytest.param(
            "incomplete",
            "max_output_tokens",
            LlmCallReasonType.MAX_TOKENS,
            id="max_tokens",
        ),
        pytest.param(
            "incomplete",
            "content_filter",
            LlmCallReasonType.CONTENT_FILTER,
            id="content_filter",
        ),
    ],
)
async def test_complete_maps_reason(
    openai_llm_service: OpenAiLlmService,
    openai_handler_stub: HttpHandlerStub,
    status: str,
    incomplete_reason: str | None,
    expected_reason: LlmCallReasonType | None,
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        status=status, incomplete_reason=incomplete_reason
    )
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.reason == expected_reason


@pytest.mark.parametrize(
    ("status", "incomplete_reason", "expected_reason"),
    [
        pytest.param("failed", None, LlmCallReasonType.PROVIDER_ERROR, id="failed"),
        pytest.param("cancelled", None, LlmCallReasonType.CANCELLED, id="cancelled"),
        pytest.param("queued", None, LlmCallReasonType.NOT_FINISHED, id="queued"),
        pytest.param(
            "incomplete",
            "steered",
            LlmCallReasonType.NOT_FINISHED,
            id="unmapped_incomplete_reason",
        ),
    ],
)
async def test_complete_unusable_status_maps_to_failure_reason(
    openai_llm_service: OpenAiLlmService,
    openai_handler_stub: HttpHandlerStub,
    status: str,
    incomplete_reason: str | None,
    expected_reason: LlmCallReasonType,
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        status=status, incomplete_reason=incomplete_reason
    )
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.reason == expected_reason


async def test_complete_refusal_returns_refusal_text_as_content(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        refusal_text="I can't help with that."
    )
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.content == "I can't help with that."
    assert complete_result.reason == LlmCallReasonType.REFUSAL


async def test_complete_missing_usage_returns_zero_token_counts(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(include_usage=False)
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.input_tokens == 0
    assert complete_result.output_tokens == 0
    assert complete_result.cached_input_tokens == 0
    assert complete_result.reasoning_tokens == 0


async def test_complete_structured_parses_into_output_type(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        output_text=json.dumps({"answer": "42"})
    )
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_structured_result = await openai_llm_service.complete_structured(
        provider_input, _SampleOutput
    )

    assert complete_structured_result.parsed_output == _SampleOutput(answer="42")


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        pytest.param(401, LlmUnavailableException, id="authentication_error"),
        pytest.param(403, LlmUnavailableException, id="permission_denied"),
        pytest.param(400, LlmFailedException, id="bad_request"),
    ],
)
async def test_complete_non_retryable_status_raises_mapped_exception_after_one_request(
    openai_llm_service: OpenAiLlmService,
    openai_handler_stub: HttpHandlerStub,
    status_code: int,
    expected_exception: type[Exception],
) -> None:
    openai_error_payload = build_openai_error_payload(message="stub provider error")
    openai_handler_stub.handle_responses.append(
        httpx.Response(status_code, json=openai_error_payload)
    )
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(expected_exception) as raised_exception_info:
        await openai_llm_service.complete(provider_input)

    assert len(openai_handler_stub.handle_requests) == 1
    raised_exception = raised_exception_info.value
    assert raised_exception.provider_message is not None
    assert "stub provider error" in raised_exception.provider_message


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        pytest.param(429, LlmRateLimitedException, id="rate_limited"),
        pytest.param(500, LlmFailedException, id="internal_server_error"),
    ],
)
async def test_complete_retryable_status_exhausted_raises_mapped_exception(
    openai_llm_service: OpenAiLlmService,
    openai_handler_stub: HttpHandlerStub,
    status_code: int,
    expected_exception: type[Exception],
) -> None:
    openai_error_payload = build_openai_error_payload(message="stub provider error")
    openai_handler_stub.handle_responses.extend(
        httpx.Response(status_code, json=openai_error_payload) for _ in range(3)
    )
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(expected_exception) as raised_exception_info:
        await openai_llm_service.complete(provider_input)

    assert len(openai_handler_stub.handle_requests) == 3
    raised_exception = raised_exception_info.value
    assert raised_exception.provider_message is not None
    assert "stub provider error" in raised_exception.provider_message


@pytest.mark.parametrize("status_code", [429, 500])
async def test_complete_retryable_status_then_success_returns_result(
    openai_llm_service: OpenAiLlmService,
    openai_handler_stub: HttpHandlerStub,
    status_code: int,
) -> None:
    openai_error_payload = build_openai_error_payload()
    openai_responses_payload = build_openai_responses_payload(output_text="Second try.")
    openai_handler_stub.handle_responses.extend(
        [
            httpx.Response(status_code, json=openai_error_payload),
            httpx.Response(200, json=openai_responses_payload),
        ]
    )
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.content == "Second try."
    assert len(openai_handler_stub.handle_requests) == 2


async def test_complete_connection_error_then_success_returns_result(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_handler_stub.handle_errors.append(httpx.ConnectError("connection failed"))
    openai_responses_payload = build_openai_responses_payload(output_text="Second try.")
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.content == "Second try."
    assert len(openai_handler_stub.handle_requests) == 2


async def test_complete_connection_error_exhausted_raises_llm_unavailable_exception(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_handler_stub.handle_error = httpx.ConnectError("connection failed")
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(LlmUnavailableException):
        await openai_llm_service.complete(provider_input)

    assert len(openai_handler_stub.handle_requests) == 3


async def test_complete_timeout_raises_llm_unavailable_exception_without_retrying(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_handler_stub.handle_error = httpx.ReadTimeout("timed out")
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(LlmUnavailableException):
        await openai_llm_service.complete(provider_input)

    assert len(openai_handler_stub.handle_requests) == 1


async def test_complete_retry_logs_llm_provider_retry(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_error_payload = build_openai_error_payload()
    openai_responses_payload = build_openai_responses_payload()
    openai_handler_stub.handle_responses.extend(
        [
            httpx.Response(429, json=openai_error_payload),
            httpx.Response(200, json=openai_responses_payload),
        ]
    )
    provider_input = build_llm_provider_completion_input()

    with structlog.testing.capture_logs() as captured_log_events:
        await openai_llm_service.complete(provider_input)

    llm_provider_retry_events = [
        log_event for log_event in captured_log_events if log_event["event"] == "llm_provider_retry"
    ]
    assert len(llm_provider_retry_events) == 1
    assert llm_provider_retry_events[0]["attempt"] == 1
    assert llm_provider_retry_events[0]["error_type"] == "RateLimitError"
    assert llm_provider_retry_events[0]["delay_seconds"] == 0


async def test_complete_structured_retryable_status_then_success_returns_parsed_output(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_error_payload = build_openai_error_payload()
    openai_responses_payload = build_openai_responses_payload(
        output_text=json.dumps({"answer": "42"})
    )
    openai_handler_stub.handle_responses.extend(
        [
            httpx.Response(500, json=openai_error_payload),
            httpx.Response(200, json=openai_responses_payload),
        ]
    )
    provider_input = build_llm_provider_completion_input()

    complete_structured_result = await openai_llm_service.complete_structured(
        provider_input, _SampleOutput
    )

    assert complete_structured_result.parsed_output == _SampleOutput(answer="42")
    assert len(openai_handler_stub.handle_requests) == 2


@pytest.mark.parametrize(
    ("reasoning_effort", "expected_reasoning"),
    [
        pytest.param(LlmReasoningEffortType.LOW, {"effort": "low"}, id="low"),
        pytest.param(LlmReasoningEffortType.MINIMAL, {"effort": "minimal"}, id="minimal"),
        pytest.param(LlmReasoningEffortType.HIGH, {"effort": "high"}, id="high"),
    ],
)
async def test_complete_reasoning_effort_sends_lowercase_effort(
    openai_llm_service: OpenAiLlmService,
    openai_handler_stub: HttpHandlerStub,
    reasoning_effort: LlmReasoningEffortType,
    expected_reasoning: dict[str, str],
) -> None:
    openai_responses_payload = build_openai_responses_payload()
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input(reasoning_effort=reasoning_effort)

    await openai_llm_service.complete(provider_input)

    sent_request_body: dict[str, Any] = json.loads(openai_handler_stub.handle_requests[0].content)
    assert sent_request_body["reasoning"] == expected_reasoning


async def test_complete_no_reasoning_effort_omits_reasoning(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload()
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input(reasoning_effort=None)

    await openai_llm_service.complete(provider_input)

    sent_request_body: dict[str, Any] = json.loads(openai_handler_stub.handle_requests[0].content)
    assert "reasoning" not in sent_request_body


async def test_complete_structured_reasoning_effort_sends_lowercase_effort(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        output_text=json.dumps({"answer": "42"})
    )
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input(
        reasoning_effort=LlmReasoningEffortType.MEDIUM
    )

    await openai_llm_service.complete_structured(provider_input, _SampleOutput)

    sent_request_body: dict[str, Any] = json.loads(openai_handler_stub.handle_requests[0].content)
    assert sent_request_body["reasoning"] == {"effort": "medium"}
