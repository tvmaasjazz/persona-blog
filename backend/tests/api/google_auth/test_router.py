from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.exceptions import AuthSignInStateExpiredException
from libs.auth.results import AuthUser
from libs.auth.types import AuthProviderType
from libs.core.exceptions import UnauthorizedException
from libs.database.orm import UserAuthProviderOrm, UserOrm
from libs.permissions.types import PermissionType, RoleType
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
        id=user_record.id,
        identity=user_record.identity,
        role=RoleType.READER,
        permissions=frozenset({PermissionType.PERSONA_READ, PermissionType.BLOG_POST_READ}),
    )


async def test_get_google_callback_known_creator_stores_role_and_permissions_in_session(
    api_client: AsyncClient, db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com", role=RoleType.CREATOR)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-stub"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    session_id = get_google_callback_response.cookies.get("sid")
    assert session_id is not None
    stored_session = await redis_client.get(f"session:{session_id}")
    assert stored_session is not None
    assert AuthUser.model_validate_json(stored_session) == AuthUser(
        id=user_record.id,
        identity=user_record.identity,
        role=RoleType.CREATOR,
        permissions=frozenset(
            {
                PermissionType.PERSONA_READ,
                PermissionType.PERSONA_WRITE,
                PermissionType.BLOG_POST_READ,
                PermissionType.BLOG_POST_WRITE,
                PermissionType.GENERATE_TEXT_RUN_READ,
                PermissionType.GENERATE_TEXT_RUN_WRITE,
            }
        ),
    )


async def test_get_google_callback_inactive_user_redirects_to_sign_in_with_account_suspended(
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

    redirect_location = urlparse(get_google_callback_response.headers["location"])
    assert get_google_callback_response.status_code == 303
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"error": ["ACCOUNT_SUSPENDED"]}
    assert get_google_callback_response.headers.get_list("set-cookie") == []


async def test_get_google_callback_email_taken_redirects_to_sign_in_with_email_taken(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await insert_user_row(db_session, email="ada@example.com")

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    redirect_location = urlparse(get_google_callback_response.headers["location"])
    assert get_google_callback_response.status_code == 303
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"error": ["EMAIL_TAKEN"]}
    assert get_google_callback_response.headers.get_list("set-cookie") == []


async def test_get_google_callback_bad_state_redirects_to_sign_in_with_sign_in_expired(
    api_client: AsyncClient, google_oauth_service_stub: GoogleOAuthServiceStub
) -> None:
    google_oauth_service_stub.exchange_code_for_identity_error = AuthSignInStateExpiredException(
        "Sign-in state is missing or expired"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "bad-state"},
        follow_redirects=False,
    )

    redirect_location = urlparse(get_google_callback_response.headers["location"])
    assert get_google_callback_response.status_code == 303
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"error": ["SIGN_IN_EXPIRED"]}
    assert get_google_callback_response.headers.get_list("set-cookie") == []


async def test_get_google_callback_google_rejects_code_redirects_to_sign_in_with_sign_in_failed(
    api_client: AsyncClient, google_oauth_service_stub: GoogleOAuthServiceStub
) -> None:
    google_oauth_service_stub.exchange_code_for_identity_error = UnauthorizedException(
        "Google rejected the code"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "bad-code", "state": "state-1"},
        follow_redirects=False,
    )

    redirect_location = urlparse(get_google_callback_response.headers["location"])
    assert get_google_callback_response.status_code == 303
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"error": ["SIGN_IN_FAILED"]}
    assert get_google_callback_response.headers.get_list("set-cookie") == []
