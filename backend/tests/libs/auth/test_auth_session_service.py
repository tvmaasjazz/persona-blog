from uuid import uuid4

import pytest
from redis.asyncio import Redis

from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException
from libs.permissions.types import PermissionType, RoleType
from tests.factories.auth import build_auth_user


async def test_create_session_stores_auth_user_json(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    user_identity = uuid4()
    auth_user = build_auth_user(
        user_id=42,
        user_identity=user_identity,
        role=RoleType.CREATOR,
        permissions=frozenset({PermissionType.PERSONA_WRITE}),
    )

    session_id = await auth_session_service.create_session(auth_user)

    stored_session = await redis_client.get(f"session:{session_id}")
    assert stored_session is not None
    assert AuthUser.model_validate_json(stored_session) == AuthUser(
        id=42,
        identity=user_identity,
        role=RoleType.CREATOR,
        permissions=frozenset({PermissionType.PERSONA_WRITE}),
    )


async def test_create_session_sets_ttl_within_setting(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings(session_ttl_seconds=600)
    )

    session_id = await auth_session_service.create_session(build_auth_user(user_id=42))

    session_ttl_seconds = await redis_client.ttl(f"session:{session_id}")
    assert 0 < session_ttl_seconds <= 600


async def test_create_session_two_calls_produce_different_session_ids(
    redis_client: Redis,
) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    auth_user = build_auth_user(user_id=42)

    first_session_id = await auth_session_service.create_session(auth_user)
    second_session_id = await auth_session_service.create_session(auth_user)

    assert first_session_id != second_session_id


async def test_find_session_returns_auth_user(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    user_identity = uuid4()
    auth_user = build_auth_user(
        user_id=42,
        user_identity=user_identity,
        role=RoleType.READER,
        permissions=frozenset({PermissionType.BLOG_POST_WRITE, PermissionType.PERSONA_WRITE}),
    )
    session_id = await auth_session_service.create_session(auth_user)

    find_session_result = await auth_session_service.find_session(session_id)

    assert find_session_result == AuthUser(
        id=42,
        identity=user_identity,
        role=RoleType.READER,
        permissions=frozenset({PermissionType.BLOG_POST_WRITE, PermissionType.PERSONA_WRITE}),
    )


async def test_find_session_stored_without_role_raises_unauthorized_exception(
    redis_client: Redis,
) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    old_session_json = f'{{"id": 42, "identity": "{uuid4()}"}}'
    await redis_client.set("session:old-session-id", old_session_json)

    with pytest.raises(UnauthorizedException):
        await auth_session_service.find_session("old-session-id")


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
    session_id = await auth_session_service.create_session(build_auth_user(user_id=42))
    await auth_session_service.delete_session(session_id)

    with pytest.raises(UnauthorizedException):
        await auth_session_service.find_session(session_id)


async def test_delete_session_removes_key(redis_client: Redis) -> None:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    session_id = await auth_session_service.create_session(build_auth_user(user_id=42))

    await auth_session_service.delete_session(session_id)

    session_exists = await redis_client.exists(f"session:{session_id}")
    assert session_exists == 0
