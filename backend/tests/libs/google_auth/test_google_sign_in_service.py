from datetime import UTC, datetime
from decimal import Decimal

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.auth.settings import AuthSettings
from libs.core.exceptions import UnauthorizedException
from libs.credits.services import CreditLedgerService
from libs.database.orm import CreditLedgerOrm, UserAuthProviderOrm, UserOrm
from libs.google_auth.services import GoogleSignInService
from libs.invites.services import InviteService
from libs.invites.types import InviteSignInResultType
from libs.invites.utils import InviteUtils
from libs.permissions.services import PermissionService
from libs.permissions.types import PermissionType, RoleType
from libs.users.services import UserActivityService, UserService
from libs.users.settings import UserSettings
from tests.factories.google_auth import build_google_identity_result
from tests.factories.invites import insert_invite_row
from tests.factories.users import insert_user_auth_provider_row, insert_user_row
from tests.stubs.google_auth import GoogleOAuthServiceStub


async def test_build_sign_in_url_without_invite_code_returns_google_authorization_url(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_oauth_service_stub.build_authorization_url_result = "https://google.example/auth?s=1"
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    sign_in_url = await google_sign_in_service.build_sign_in_url(None)

    assert sign_in_url == "https://google.example/auth?s=1"
    assert google_oauth_service_stub.build_authorization_url_inputs == [None]


async def test_build_sign_in_url_usable_invite_returns_google_url_carrying_code(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    await insert_invite_row(db_session, code_hash=InviteUtils.hash_code("known-code"))
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_oauth_service_stub.build_authorization_url_result = "https://google.example/auth?s=1"
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    sign_in_url = await google_sign_in_service.build_sign_in_url("known-code")

    assert sign_in_url == "https://google.example/auth?s=1"
    assert google_oauth_service_stub.build_authorization_url_inputs == ["known-code"]


async def test_build_sign_in_url_unknown_invite_returns_sign_in_url_with_not_found_error(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    sign_in_url = await google_sign_in_service.build_sign_in_url("unknown-code")

    assert sign_in_url == "https://app.example.com/sign-in?invite_error=INVITE_NOT_FOUND"
    assert google_oauth_service_stub.build_authorization_url_inputs == []


async def test_build_sign_in_url_used_invite_returns_sign_in_url_with_used_error(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    earlier_user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        used_at=datetime(2026, 1, 2, tzinfo=UTC),
        used_by_user_id=earlier_user_record.id,
    )
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    sign_in_url = await google_sign_in_service.build_sign_in_url("known-code")

    assert sign_in_url == "https://app.example.com/sign-in?invite_error=INVITE_USED"
    assert google_oauth_service_stub.build_authorization_url_inputs == []


@pytest.mark.parametrize(
    ("expires_at", "revoked_at", "expected_sign_in_url"),
    [
        pytest.param(
            datetime(2026, 1, 2, tzinfo=UTC),
            None,
            "https://app.example.com/sign-in?invite_error=INVITE_EXPIRED",
            id="expired",
        ),
        pytest.param(
            datetime(2099, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
            "https://app.example.com/sign-in?invite_error=INVITE_REVOKED",
            id="revoked",
        ),
    ],
)
async def test_build_sign_in_url_expired_or_revoked_invite_returns_sign_in_url_with_reason(
    db_session: AsyncSession,
    redis_client: Redis,
    expires_at: datetime,
    revoked_at: datetime | None,
    expected_sign_in_url: str,
) -> None:
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    sign_in_url = await google_sign_in_service.build_sign_in_url("known-code")

    assert sign_in_url == expected_sign_in_url
    assert google_oauth_service_stub.build_authorization_url_inputs == []


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
        id=user_record.id,
        identity=user_record.identity,
        role=RoleType.READER,
        permissions=frozenset({PermissionType.PERSONA_READ, PermissionType.BLOG_POST_READ}),
    )
    assert google_sign_in_result.is_new_user is True
    assert user_record.last_login_at is not None
    assert user_auth_provider_record.last_used_at is not None


async def test_sign_in_with_google_known_creator_stores_role_and_permissions_in_session(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com", role=RoleType.CREATOR)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-stub"
    )
    google_sign_in_service = _build_google_sign_in_service(db_session, redis_client)

    google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-1", "state-1"
    )

    stored_session = await redis_client.get(f"session:{google_sign_in_result.session_id}")
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


async def test_sign_in_with_google_without_invite_code_returns_no_invite_result(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    google_sign_in_service = _build_google_sign_in_service(db_session, redis_client)

    google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-1", "state-1"
    )

    assert google_sign_in_result.invite_sign_in_result_type is None


async def test_sign_in_with_google_new_identity_with_invite_creates_creator_and_redeems_invite(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    invite_record = await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        credit_amount_usd=Decimal("7.50"),
    )
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_oauth_service_stub.exchange_code_for_identity_result = build_google_identity_result(
        invite_code="known-code"
    )
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-1", "state-1"
    )

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    user_record = await db_session.scalar(user_query)
    assert user_record is not None
    await db_session.refresh(invite_record)
    stored_session = await redis_client.get(f"session:{google_sign_in_result.session_id}")
    assert stored_session is not None
    session_auth_user = AuthUser.model_validate_json(stored_session)
    assert session_auth_user.role == RoleType.CREATOR
    assert PermissionType.PERSONA_WRITE in session_auth_user.permissions
    assert google_sign_in_result.invite_sign_in_result_type == InviteSignInResultType.ACCEPTED
    assert invite_record.used_by_user_id == user_record.id
    assert user_record.credit_balance_usd == Decimal("7.50")


async def test_sign_in_with_google_known_reader_with_invite_becomes_creator(
    db_session: AsyncSession, redis_client: Redis
) -> None:
    user_record = await insert_user_row(db_session, email="ada@example.com", role=RoleType.READER)
    await insert_user_auth_provider_row(
        db_session, user_id=user_record.id, provider_subject="google-subject-stub"
    )
    await insert_invite_row(db_session, code_hash=InviteUtils.hash_code("known-code"))
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_oauth_service_stub.exchange_code_for_identity_result = build_google_identity_result(
        invite_code="known-code"
    )
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-1", "state-1"
    )

    stored_session = await redis_client.get(f"session:{google_sign_in_result.session_id}")
    assert stored_session is not None
    assert AuthUser.model_validate_json(stored_session).role == RoleType.CREATOR
    assert google_sign_in_result.is_new_user is False


@pytest.mark.parametrize(
    ("invite_code", "expected_invite_sign_in_result_type"),
    [
        pytest.param("used-code", InviteSignInResultType.INVITE_USED, id="used"),
        pytest.param("unknown-code", InviteSignInResultType.INVITE_NOT_FOUND, id="unknown"),
    ],
)
async def test_sign_in_with_google_unusable_invite_still_signs_in_as_reader_without_grant(
    db_session: AsyncSession,
    redis_client: Redis,
    invite_code: str,
    expected_invite_sign_in_result_type: InviteSignInResultType,
) -> None:
    earlier_user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("used-code"),
        used_at=datetime(2026, 1, 2, tzinfo=UTC),
        used_by_user_id=earlier_user_record.id,
    )
    google_oauth_service_stub = GoogleOAuthServiceStub()
    google_oauth_service_stub.exchange_code_for_identity_result = build_google_identity_result(
        invite_code=invite_code
    )
    google_sign_in_service = _build_google_sign_in_service(
        db_session, redis_client, google_oauth_service_stub=google_oauth_service_stub
    )

    google_sign_in_result = await google_sign_in_service.sign_in_with_google(
        "auth-code-1", "state-1"
    )

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    user_record = await db_session.scalar(user_query)
    assert user_record is not None
    ledger_count_query = select(func.count(CreditLedgerOrm.id)).where(
        CreditLedgerOrm.user_id == user_record.id
    )
    ledger_row_count = await db_session.scalar(ledger_count_query)
    stored_session = await redis_client.get(f"session:{google_sign_in_result.session_id}")
    assert stored_session is not None
    assert AuthUser.model_validate_json(stored_session).role == RoleType.READER
    assert google_sign_in_result.invite_sign_in_result_type == expected_invite_sign_in_result_type
    assert ledger_row_count == 0


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
    user_service = UserService(
        db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
    )
    invite_service = InviteService(
        db_session=db_session,
        credit_ledger_service=CreditLedgerService(db_session=db_session),
        user_service=user_service,
    )
    return GoogleSignInService(
        google_oauth_service=google_oauth_service_stub or GoogleOAuthServiceStub(),
        user_service=user_service,
        user_activity_service=user_activity_service,
        auth_session_service=auth_session_service,
        permission_service=PermissionService(db_session=db_session),
        invite_service=invite_service,
        frontend_url="https://app.example.com",
    )
