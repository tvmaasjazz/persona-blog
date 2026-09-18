import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException
from libs.database.orm import UserAuthProviderOrm, UserOrm
from libs.google_auth.services import GoogleSignInService
from libs.users.services import UserActivityService, UserService
from libs.users.settings import UserSettings
from tests.stubs.google_auth import GoogleOAuthServiceStub


async def test_sign_in_with_google_new_identity_creates_user_and_session(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    google_sign_in_service = _build_google_sign_in_service(db_session, redis_client)

    google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-1", "state-1"
    )

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    user_record = await db_session.scalar(user_query)
    assert user_record is not None
    user_auth_provider_query = select(UserAuthProviderOrm).where(
        UserAuthProviderOrm.user_id == user_record.id
    )
    user_auth_provider_record = await db_session.scalar(user_auth_provider_query)
    assert user_auth_provider_record is not None
    stored_session = await redis_client.get(f"session:{google_sign_in_result.session_id}")
    assert stored_session is not None
    assert AuthUser.model_validate_json(stored_session) == AuthUser(
        id=user_record.id, identity=user_record.identity
    )
    assert google_sign_in_result.is_new_user is True
    assert user_record.last_login_at is not None
    assert user_auth_provider_record.last_used_at is not None


async def test_sign_in_with_google_known_identity_reuses_user(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    google_sign_in_service = _build_google_sign_in_service(db_session, redis_client)
    first_google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-1", "state-1"
    )

    second_google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-2", "state-2"
    )

    user_count_query = select(func.count(UserOrm.id)).where(UserOrm.email == "ada@example.com")
    user_count = await db_session.scalar(user_count_query)
    assert second_google_sign_in_result.is_new_user is False
    assert second_google_sign_in_result.session_id != first_google_sign_in_result.session_id
    assert user_count == 1


async def test_sign_in_with_google_bad_state_raises_unauthorized_exception(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_oauth_service_stub.exchange_code_for_identity_error = UnauthorizedException(
        "Sign-in state is missing or expired"
    )
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    with pytest.raises(UnauthorizedException):
        await google_sign_in_service.sign_in_with_google("auth-code-1", "bad-state")


def _build_google_sign_in_service(
    db_session: AsyncSession,
    redis_client: Redis,
    *,
    google_oauth_service_stub: GoogleOAuthServiceStub | None = None,
) -> GoogleSignInService:
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=AuthSettings()
    )
    user_activity_service = UserActivityService(
        db_session=db_session, redis_client=redis_client, user_settings=UserSettings()
    )
    return GoogleSignInService(
        google_oauth_service=google_oauth_service_stub or GoogleOAuthServiceStub(),
        user_service=UserService(db_session=db_session),
        user_activity_service=user_activity_service,
        auth_session_service=auth_session_service,
    )
