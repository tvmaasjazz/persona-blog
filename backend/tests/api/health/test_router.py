from httpx import AsyncClient


async def test_get_health_returns_status_and_settings(api_client: AsyncClient) -> None:
    get_health_response = await api_client.get("/health")

    assert get_health_response.status_code == 200
    assert get_health_response.json() == {
        "status": "OK",
        "app_name": "Persona Blog API",
        "environment": "test",
    }
