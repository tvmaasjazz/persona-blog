from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.auth.types import AuthProviderType
from libs.core.exceptions import UnauthorizedException
from libs.database.orm import UserAuthProviderOrm, UserOrm
from tests.factories.users import insert_user_auth_provider_row, insert_user_row
from tests.stubs.google_auth import GoogleOAuthServiceStub


async def test_get_google_login_redirects_to_google_authorization_url(
    api_client: AsyncClient, google_oauth_service_stub: GoogleOAuthServiceStub
) -> None:
    get_google_login_response = await api_client.get("/auth/google/login", follow_redirects=False)

    assert get_google_login_response.status_code == 307
    assert get_google_login_response.headers["location"] == (
        google_oauth_service_stub.build_authorization_url_result
    )


async def test_get_google_callback_first_time_identity_creates_user_and_session(
    api_client: AsyncClient, db_session: AsyncSession, redis_client: Redis
) -> None:
    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    user_record = await db_session.scalar(user_query)
    assert user_record is not None
    user_auth_provider_query = select(UserAuthProviderOrm).where(
        UserAuthProviderOrm.user_id == user_record.id
    )
    user_auth_provider_record = await db_session.scalar(user_auth_provider_query)
    assert user_auth_provider_record is not None
    assert user_auth_provider_record.provider == AuthProviderType.GOOGLE
    assert user_auth_provider_record.provider_subject == "google-subject-stub"

    assert get_google_callback_response.status_code == 303
    assert get_google_callback_response.headers["location"] == "http://localhost:5173"

    set_cookie_header = get_google_callback_response.headers.get_list("set-cookie")[0]
    assert "sid=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header
    assert "Max-Age=" in set_cookie_header
    assert "Secure" in set_cookie_header

    session_id = get_google_callback_response.cookies.get("sid")
    assert session_id is not None
    stored_session = await redis_client.get(f"session:{session_id}")
    assert stored_session is not None
    assert AuthUser.model_validate_json(stored_session) == AuthUser(
        id=user_record.id, identity=user_record.identity
    )


async def test_get_google_callback_inactive_user_returns_403(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com", is_active=False)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-stub"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    assert get_google_callback_response.status_code == 403


async def test_get_google_callback_email_taken_by_another_user_returns_409(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await insert_user_row(db_session, email="ada@example.com")

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    assert get_google_callback_response.status_code == 409


async def test_get_google_callback_bad_state_returns_401(
    api_client: AsyncClient, google_oauth_service_stub: GoogleOAuthServiceStub
) -> None:
    google_oauth_service_stub.exchange_code_for_identity_error = UnauthorizedException(
        "Sign-in state is missing or expired"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "bad-state"},
        follow_redirects=False,
    )

    assert get_google_callback_response.status_code == 401
