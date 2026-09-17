import pytest
from redis.asyncio import Redis

from libs.auth.results import OAuthStateResult
from libs.auth.services import OAuthStateService
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException


async def test_create_state_two_calls_produce_distinct_values(redis_client: Redis) -> None:
    oauth_state_service = OAuthStateService(redis_client=redis_client, auth_settings=AuthSettings())

    first_oauth_state_result = await oauth_state_service.create_state()
    second_oauth_state_result = await oauth_state_service.create_state()

    assert first_oauth_state_result.oauth_state != second_oauth_state_result.oauth_state
    assert first_oauth_state_result.nonce != second_oauth_state_result.nonce
    assert first_oauth_state_result.code_verifier != second_oauth_state_result.code_verifier


async def test_create_state_stores_record_with_ttl(redis_client: Redis) -> None:
    oauth_state_service = OAuthStateService(
        redis_client=redis_client, auth_settings=AuthSettings(oauth_state_ttl_seconds=120)
    )

    oauth_state_result = await oauth_state_service.create_state()

    stored_state = await redis_client.get(f"oauth-state:{oauth_state_result.oauth_state}")
    state_ttl_seconds = await redis_client.ttl(f"oauth-state:{oauth_state_result.oauth_state}")
    assert stored_state is not None
    assert OAuthStateResult.model_validate_json(stored_state) == oauth_state_result
    assert 0 < state_ttl_seconds <= 120


async def test_consume_state_returns_stored_result_and_deletes_key(redis_client: Redis) -> None:
    oauth_state_service = OAuthStateService(redis_client=redis_client, auth_settings=AuthSettings())
    oauth_state_result = await oauth_state_service.create_state()

    consume_state_result = await oauth_state_service.consume_state(oauth_state_result.oauth_state)

    assert consume_state_result == oauth_state_result
    with pytest.raises(UnauthorizedException):
        await oauth_state_service.consume_state(oauth_state_result.oauth_state)


async def test_consume_state_unknown_state_raises_unauthorized_exception(
    redis_client: Redis,
) -> None:
    oauth_state_service = OAuthStateService(redis_client=redis_client, auth_settings=AuthSettings())

    with pytest.raises(UnauthorizedException):
        await oauth_state_service.consume_state("unknown-state")
