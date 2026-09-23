import json

import httpx2
import pytest
from pydantic import BaseModel

from libs.llm.exceptions import (
    LlmFailedException,
    LlmRateLimitedException,
    LlmUnavailableException,
)
from libs.llm.results import LlmProviderCompletionResult
from libs.llm.types import LlmCallReasonType
from libs.openai_llm.services import OpenAiLlmService
from tests.factories.llm import build_llm_provider_completion_input
from tests.payloads.openai import build_openai_error_payload, build_openai_responses_payload
from tests.stubs.http2 import Httpx2HandlerStub


class _SampleOutput(BaseModel):
    answer: str


async def test_complete_returns_content_and_token_counts(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: Httpx2HandlerStub
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
        httpx2.Response(200, json=openai_responses_payload, headers={"x-request-id": "req-abc123"})
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
    openai_handler_stub: Httpx2HandlerStub,
    status: str,
    incomplete_reason: str | None,
    expected_reason: LlmCallReasonType | None,
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        status=status, incomplete_reason=incomplete_reason
    )
    openai_handler_stub.handle_responses.append(httpx2.Response(200, json=openai_responses_payload))
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
    openai_handler_stub: Httpx2HandlerStub,
    status: str,
    incomplete_reason: str | None,
    expected_reason: LlmCallReasonType,
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        status=status, incomplete_reason=incomplete_reason
    )
    openai_handler_stub.handle_responses.append(httpx2.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.reason == expected_reason


async def test_complete_refusal_returns_refusal_text_as_content(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: Httpx2HandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        refusal_text="I can't help with that."
    )
    openai_handler_stub.handle_responses.append(httpx2.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.content == "I can't help with that."
    assert complete_result.reason == LlmCallReasonType.REFUSAL


async def test_complete_missing_usage_returns_zero_token_counts(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: Httpx2HandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(include_usage=False)
    openai_handler_stub.handle_responses.append(httpx2.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_result = await openai_llm_service.complete(provider_input)

    assert complete_result.input_tokens == 0
    assert complete_result.output_tokens == 0
    assert complete_result.cached_input_tokens == 0
    assert complete_result.reasoning_tokens == 0


async def test_complete_structured_parses_into_output_type(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: Httpx2HandlerStub
) -> None:
    openai_responses_payload = build_openai_responses_payload(
        output_text=json.dumps({"answer": "42"})
    )
    openai_handler_stub.handle_responses.append(httpx2.Response(200, json=openai_responses_payload))
    provider_input = build_llm_provider_completion_input()

    complete_structured_result = await openai_llm_service.complete_structured(
        provider_input, _SampleOutput
    )

    assert complete_structured_result.parsed_output == _SampleOutput(answer="42")


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        pytest.param(429, LlmRateLimitedException, id="rate_limited"),
        pytest.param(401, LlmUnavailableException, id="authentication_error"),
        pytest.param(403, LlmUnavailableException, id="permission_denied"),
        pytest.param(500, LlmFailedException, id="internal_server_error"),
    ],
)
async def test_complete_error_status_raises_mapped_exception(
    openai_llm_service: OpenAiLlmService,
    openai_handler_stub: Httpx2HandlerStub,
    status_code: int,
    expected_exception: type[Exception],
) -> None:
    openai_error_payload = build_openai_error_payload()
    openai_handler_stub.handle_responses.append(
        httpx2.Response(status_code, json=openai_error_payload)
    )
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(expected_exception):
        await openai_llm_service.complete(provider_input)

    assert len(openai_handler_stub.handle_requests) == 1


async def test_complete_timeout_raises_llm_unavailable_exception(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: Httpx2HandlerStub
) -> None:
    openai_handler_stub.handle_error = httpx2.ReadTimeout("timed out")
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(LlmUnavailableException):
        await openai_llm_service.complete(provider_input)


async def test_complete_connection_error_raises_llm_unavailable_exception(
    openai_llm_service: OpenAiLlmService, openai_handler_stub: Httpx2HandlerStub
) -> None:
    openai_handler_stub.handle_error = httpx2.ConnectError("connection failed")
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(LlmUnavailableException):
        await openai_llm_service.complete(provider_input)


async def test_complete_no_client_raises_llm_unavailable_exception() -> None:
    openai_llm_service = OpenAiLlmService(openai_client=None)
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(LlmUnavailableException):
        await openai_llm_service.complete(provider_input)


async def test_complete_structured_no_client_raises_llm_unavailable_exception() -> None:
    openai_llm_service = OpenAiLlmService(openai_client=None)
    provider_input = build_llm_provider_completion_input()

    with pytest.raises(LlmUnavailableException):
        await openai_llm_service.complete_structured(provider_input, _SampleOutput)
