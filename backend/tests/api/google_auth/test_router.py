from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.exceptions import AuthSignInStateExpiredException
from libs.auth.results import AuthUser, OAuthStateResult
from libs.auth.types import AuthProviderType
from libs.core.exceptions import UnauthorizedException
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm import CreditLedgerOrm, RoleOrm, UserAuthProviderOrm, UserOrm
from libs.invites.utils import InviteUtils
from libs.permissions.types import PermissionType, RoleType
from tests.factories.google_auth import build_google_identity_result
from tests.factories.invites import insert_invite_row
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


async def _find_stored_oauth_states(redis_client: Redis) -> list[OAuthStateResult]:
    oauth_state_keys = await redis_client.keys("oauth-state:*")
    stored_states = [
        await redis_client.get(oauth_state_key) for oauth_state_key in oauth_state_keys
    ]
    return [OAuthStateResult.model_validate_json(stored_state) for stored_state in stored_states]


async def test_get_google_login_usable_invite_redirects_to_google_and_stores_code_in_state(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    google_oauth_service_stub: GoogleOAuthServiceStub,
) -> None:
    await insert_invite_row(db_session, code_hash=InviteUtils.hash_code("known-code"))

    get_google_login_response = await api_client.get(
        "/auth/google/login", params={"invite_code": "known-code"}, follow_redirects=False
    )

    stored_oauth_states = await _find_stored_oauth_states(redis_client)
    assert get_google_login_response.status_code == 307
    assert get_google_login_response.headers["location"] == (
        google_oauth_service_stub.build_authorization_url_result
    )
    assert [stored_state.invite_code for stored_state in stored_oauth_states] == ["known-code"]


async def test_get_google_login_without_invite_stores_state_without_code(
    api_client: AsyncClient, redis_client: Redis
) -> None:
    await api_client.get("/auth/google/login", follow_redirects=False)

    stored_oauth_states = await _find_stored_oauth_states(redis_client)
    assert [stored_state.invite_code for stored_state in stored_oauth_states] == [None]


async def test_get_google_login_unknown_invite_redirects_to_sign_in_and_stores_no_state(
    api_client: AsyncClient, redis_client: Redis
) -> None:
    get_google_login_response = await api_client.get(
        "/auth/google/login", params={"invite_code": "unknown-code"}, follow_redirects=False
    )

    redirect_location = urlparse(get_google_login_response.headers["location"])
    stored_oauth_states = await _find_stored_oauth_states(redis_client)
    assert get_google_login_response.status_code == 307
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"invite_error": ["INVITE_NOT_FOUND"]}
    assert stored_oauth_states == []


async def test_get_google_login_used_invite_redirects_to_sign_in_and_stores_no_state(
    api_client: AsyncClient, db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        used_at=datetime(2026, 1, 2, tzinfo=UTC),
        used_by_user_id=user_record.id,
    )

    get_google_login_response = await api_client.get(
        "/auth/google/login", params={"invite_code": "known-code"}, follow_redirects=False
    )

    redirect_location = urlparse(get_google_login_response.headers["location"])
    stored_oauth_states = await _find_stored_oauth_states(redis_client)
    assert get_google_login_response.status_code == 307
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"invite_error": ["INVITE_USED"]}
    assert stored_oauth_states == []


async def test_get_google_login_expired_invite_redirects_to_sign_in_and_stores_no_state(
    api_client: AsyncClient, db_session: AsyncSession, redis_client: Redis
) -> None:
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        expires_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    get_google_login_response = await api_client.get(
        "/auth/google/login", params={"invite_code": "known-code"}, follow_redirects=False
    )

    redirect_location = urlparse(get_google_login_response.headers["location"])
    stored_oauth_states = await _find_stored_oauth_states(redis_client)
    assert get_google_login_response.status_code == 307
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"invite_error": ["INVITE_EXPIRED"]}
    assert stored_oauth_states == []


async def test_get_google_login_revoked_invite_redirects_to_sign_in_and_stores_no_state(
    api_client: AsyncClient, db_session: AsyncSession, redis_client: Redis
) -> None:
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        revoked_at=datetime(2026, 1, 2, tzinfo=UTC),
    )

    get_google_login_response = await api_client.get(
        "/auth/google/login", params={"invite_code": "known-code"}, follow_redirects=False
    )

    redirect_location = urlparse(get_google_login_response.headers["location"])
    stored_oauth_states = await _find_stored_oauth_states(redis_client)
    assert get_google_login_response.status_code == 307
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"invite_error": ["INVITE_REVOKED"]}
    assert stored_oauth_states == []


async def test_get_google_callback_new_user_with_invite_signs_in_as_creator_and_redeems_invite(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    google_oauth_service_stub: GoogleOAuthServiceStub,
) -> None:
    invite_record = await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        credit_amount_usd=Decimal("7.50"),
        note="Welcome to the beta",
    )
    google_oauth_service_stub.exchange_code_for_identity_result = build_google_identity_result(
        invite_code="known-code"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    user_record = await db_session.scalar(user_query)
    assert user_record is not None
    await db_session.refresh(invite_record)
    role_code_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == user_record.id)
    )
    saved_role_code = await db_session.scalar(role_code_query)
    ledger_query = select(CreditLedgerOrm).where(CreditLedgerOrm.user_id == user_record.id)
    ledger_record = await db_session.scalar(ledger_query)
    session_id = get_google_callback_response.cookies.get("sid")
    assert session_id is not None
    stored_session = await redis_client.get(f"session:{session_id}")
    assert stored_session is not None
    redirect_location = urlparse(get_google_callback_response.headers["location"])
    assert get_google_callback_response.status_code == 303
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"invite": ["ACCEPTED"]}
    assert AuthUser.model_validate_json(stored_session).role == RoleType.CREATOR
    assert saved_role_code == RoleType.CREATOR
    assert invite_record.used_by_user_id == user_record.id
    assert ledger_record is not None
    assert ledger_record.entry_type == CreditLedgerEntryType.GRANT
    assert ledger_record.amount_usd == Decimal("7.50")
    assert ledger_record.note == "Welcome to the beta"
    assert ledger_record.invite_id == invite_record.id
    assert user_record.credit_balance_usd == Decimal("7.50")


async def test_get_google_callback_known_reader_with_invite_becomes_creator(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    google_oauth_service_stub: GoogleOAuthServiceStub,
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com", role=RoleType.READER)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-stub"
    )
    await insert_invite_row(db_session, code_hash=InviteUtils.hash_code("known-code"))
    google_oauth_service_stub.exchange_code_for_identity_result = build_google_identity_result(
        invite_code="known-code"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    role_code_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == user_record.id)
    )
    saved_role_code = await db_session.scalar(role_code_query)
    session_id = get_google_callback_response.cookies.get("sid")
    assert session_id is not None
    stored_session = await redis_client.get(f"session:{session_id}")
    assert stored_session is not None
    redirect_location = urlparse(get_google_callback_response.headers["location"])
    assert parse_qs(redirect_location.query) == {"invite": ["ACCEPTED"]}
    assert AuthUser.model_validate_json(stored_session).role == RoleType.CREATOR
    assert saved_role_code == RoleType.CREATOR


async def test_get_google_callback_invite_used_since_login_redirects_with_invite_used_error(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    google_oauth_service_stub: GoogleOAuthServiceStub,
) -> None:
    earlier_user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        used_at=datetime(2026, 1, 2, tzinfo=UTC),
        used_by_user_id=earlier_user_record.id,
    )
    google_oauth_service_stub.exchange_code_for_identity_result = build_google_identity_result(
        invite_code="known-code"
    )

    get_google_callback_response = await api_client.get(
        "/auth/google/callback",
        params={"code": "auth-code-1", "state": "state-1"},
        follow_redirects=False,
    )

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    user_record = await db_session.scalar(user_query)
    assert user_record is not None
    ledger_count_query = select(func.count(CreditLedgerOrm.id)).where(
        CreditLedgerOrm.user_id == user_record.id
    )
    ledger_row_count = await db_session.scalar(ledger_count_query)
    session_id = get_google_callback_response.cookies.get("sid")
    assert session_id is not None
    stored_session = await redis_client.get(f"session:{session_id}")
    assert stored_session is not None
    redirect_location = urlparse(get_google_callback_response.headers["location"])
    assert get_google_callback_response.status_code == 303
    assert redirect_location.path == "/sign-in"
    assert parse_qs(redirect_location.query) == {"invite_error": ["INVITE_USED"]}
    assert AuthUser.model_validate_json(stored_session).role == RoleType.READER
    assert ledger_row_count == 0
