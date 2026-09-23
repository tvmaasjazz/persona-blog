from httpx import ASGITransport, AsyncClient

from apps.api.app_factory import create_app
from libs.database.orm import UserOrm
from libs.llm.exceptions import LlmRefusedException, LlmUnavailableException
from tests.factories.llm import build_llm_completion_result
from tests.stubs.llm import LlmServiceStub


async def test_complete_llm_returns_completion_response(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(
        content="Hello there.", input_tokens=100, output_tokens=50
    )

    complete_llm_response = await api_client.post(
        "/dev/llm/complete",
        json={"llm_type": "FAST", "system_prompt": "Be helpful.", "user_prompt": "Say hi."},
    )

    assert complete_llm_response.status_code == 200
    assert complete_llm_response.json() == {
        "llm_call_identity": str(llm_service_stub.complete_result.llm_call_identity),
        "content": "Hello there.",
        "input_tokens": 100,
        "output_tokens": 50,
    }


async def test_complete_llm_signed_out_returns_401(api_client: AsyncClient) -> None:
    complete_llm_response = await api_client.post(
        "/dev/llm/complete",
        json={"llm_type": "FAST", "system_prompt": None, "user_prompt": "Say hi."},
    )

    assert complete_llm_response.status_code == 401


async def test_complete_llm_invalid_llm_type_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    complete_llm_response = await api_client.post(
        "/dev/llm/complete",
        json={"llm_type": "MEDIUM", "system_prompt": None, "user_prompt": "Say hi."},
    )

    response_body = complete_llm_response.json()
    assert complete_llm_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["body", "llm_type"]


async def test_complete_llm_provider_unavailable_returns_503(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_error = LlmUnavailableException("The LLM provider is unavailable")

    complete_llm_response = await api_client.post(
        "/dev/llm/complete",
        json={"llm_type": "FAST", "system_prompt": None, "user_prompt": "Say hi."},
    )

    assert complete_llm_response.status_code == 503


async def test_complete_llm_provider_unavailable_response_hides_provider_message(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_error = LlmUnavailableException(
        "The LLM provider is unavailable", provider_message="upstream said no capacity"
    )

    complete_llm_response = await api_client.post(
        "/dev/llm/complete",
        json={"llm_type": "FAST", "system_prompt": None, "user_prompt": "Say hi."},
    )

    assert complete_llm_response.status_code == 503
    assert complete_llm_response.json() == {"detail": "The LLM provider is unavailable"}


async def test_complete_llm_refused_returns_422(
    api_client: AsyncClient, signed_in_user: UserOrm, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_error = LlmRefusedException(
        "The model refused to complete this request"
    )

    complete_llm_response = await api_client.post(
        "/dev/llm/complete",
        json={"llm_type": "FAST", "system_prompt": None, "user_prompt": "Say hi."},
    )

    assert complete_llm_response.status_code == 422


async def test_complete_llm_route_absent_when_environment_not_development() -> None:
    fastapi_app = create_app()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        api_transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=api_transport, base_url="https://test") as api_client:
            complete_llm_response = await api_client.post(
                "/dev/llm/complete",
                json={"llm_type": "FAST", "system_prompt": None, "user_prompt": "Say hi."},
            )

    assert complete_llm_response.status_code == 404
