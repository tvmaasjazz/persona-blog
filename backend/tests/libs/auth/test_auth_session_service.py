from uuid import uuid4

import pytest
from redis.asyncio import Redis

from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException


async def test_create_session_stores_auth_user_json(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    user_identity = uuid4()

    session_id = await auth_session_service.create_session(user_id=42, user_identity=user_identity)

    stored_session = await redis_client.get(f"session:{session_id}")
    assert stored_session is not None
    assert AuthUser.model_validate_json(stored_session) == AuthUser(id=42, identity=user_identity)


async def test_create_session_sets_ttl_within_setting(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings(session_ttl_seconds=600)
    )

    session_id = await auth_session_service.create_session(user_id=42, user_identity=uuid4())

    session_ttl_seconds = await redis_client.ttl(f"session:{session_id}")
    assert 0 < session_ttl_seconds <= 600


async def test_create_session_two_calls_produce_different_session_ids(
    redis_client: Redis,
) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    user_identity = uuid4()

    first_session_id = await auth_session_service.create_session(
        user_id=42, user_identity=user_identity
    )
    second_session_id = await auth_session_service.create_session(
        user_id=42, user_identity=user_identity
    )

    assert first_session_id != second_session_id


async def test_find_session_returns_auth_user(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    user_identity = uuid4()
    session_id = await auth_session_service.create_session(user_id=42, user_identity=user_identity)

    find_session_result = await auth_session_service.find_session(session_id)

    assert find_session_result == AuthUser(id=42, identity=user_identity)


async def test_find_session_missing_key_raises_unauthorized_exception(
    redis_client: Redis,
) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )

    with pytest.raises(UnauthorizedException):
        await auth_session_service.find_session("unknown-session-id")


async def test_find_session_deleted_key_raises_unauthorized_exception(
    redis_client: Redis,
) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    session_id = await auth_session_service.create_session(user_id=42, user_identity=uuid4())
    await auth_session_service.delete_session(session_id)

    with pytest.raises(UnauthorizedException):
        await auth_session_service.find_session(session_id)


async def test_delete_session_removes_key(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    session_id = await auth_session_service.create_session(user_id=42, user_identity=uuid4())

    await auth_session_service.delete_session(session_id)

    session_exists = await redis_client.exists(f"session:{session_id}")
    assert session_exists == 0
