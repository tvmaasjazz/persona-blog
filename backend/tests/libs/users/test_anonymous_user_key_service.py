from redis.asyncio import Redis

from libs.users.services import AnonymousUserKeyService

SECONDS_PER_DAY = 24 * 60 * 60


async def test_build_anonymous_user_key_same_visitor_returns_same_key(redis_client: Redis) -> None:
    anonymous_user_key_service = AnonymousUserKeyService(redis_client=redis_client)

    first_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "Mozilla/5.0"
    )
    second_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "Mozilla/5.0"
    )

    assert first_anonymous_user_key == second_anonymous_user_key
    assert len(first_anonymous_user_key) == 64


async def test_build_anonymous_user_key_different_ip_returns_different_key(
    redis_client: Redis,
) -> None:
    anonymous_user_key_service = AnonymousUserKeyService(redis_client=redis_client)

    first_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "Mozilla/5.0"
    )
    second_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.8", "Mozilla/5.0"
    )

    assert first_anonymous_user_key != second_anonymous_user_key


async def test_build_anonymous_user_key_different_user_agent_returns_different_key(
    redis_client: Redis,
) -> None:
    anonymous_user_key_service = AnonymousUserKeyService(redis_client=redis_client)

    first_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "Mozilla/5.0"
    )
    second_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "curl/8.0"
    )

    assert first_anonymous_user_key != second_anonymous_user_key


async def test_build_anonymous_user_key_stores_salt_expiring_by_next_midnight(
    redis_client: Redis,
) -> None:
    anonymous_user_key_service = AnonymousUserKeyService(redis_client=redis_client)

    await anonymous_user_key_service.build_anonymous_user_key("203.0.113.7", "Mozilla/5.0")

    salt_keys = await redis_client.keys("anonymous-user-key-salt:*")
    salt_ttl_seconds = await redis_client.ttl(salt_keys[0])
    assert len(salt_keys) == 1
    assert 0 < salt_ttl_seconds <= SECONDS_PER_DAY


async def test_build_anonymous_user_key_salt_gone_returns_different_key(
    redis_client: Redis,
) -> None:
    anonymous_user_key_service = AnonymousUserKeyService(redis_client=redis_client)
    first_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "Mozilla/5.0"
    )
    salt_keys = await redis_client.keys("anonymous-user-key-salt:*")
    await redis_client.delete(*salt_keys)

    second_anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "Mozilla/5.0"
    )

    assert first_anonymous_user_key != second_anonymous_user_key


async def test_build_anonymous_user_key_does_not_expose_ip(redis_client: Redis) -> None:
    anonymous_user_key_service = AnonymousUserKeyService(redis_client=redis_client)

    anonymous_user_key = await anonymous_user_key_service.build_anonymous_user_key(
        "203.0.113.7", "Mozilla/5.0"
    )

    redis_keys = await redis_client.keys("*")
    redis_values = [await redis_client.get(redis_key) for redis_key in redis_keys]
    stored_text = " ".join(str(stored_item) for stored_item in [*redis_keys, *redis_values])
    assert "203.0.113.7" not in anonymous_user_key
    assert "203.0.113.7" not in stored_text
