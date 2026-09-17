from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.types import AuthProviderType
from libs.database.orm import UserAuthProviderOrm, UserOrm
from libs.users.inputs import FindOrCreateUserFromAuthProviderInput


async def insert_user_row(
    db_session: AsyncSession,
    *,
    email: str | None = None,
    display_name: str | None = "Ada Lovelace",
    last_login_at: datetime | None = None,
    deleted_at: datetime | None = None,
    is_active: bool = True,
) -> UserOrm:
    user_record = UserOrm(
        email=email or _build_unique_email(),
        display_name=display_name,
        last_login_at=last_login_at,
        deleted_at=deleted_at,
        is_active=is_active,
    )
    db_session.add(user_record)
    await db_session.flush()
    return user_record


async def insert_user_auth_provider_row(
    db_session: AsyncSession,
    *,
    user_id: int,
    provider: AuthProviderType = AuthProviderType.GOOGLE,
    provider_subject: str | None = None,
    email_at_provider: str | None = None,
    deleted_at: datetime | None = None,
) -> UserAuthProviderOrm:
    user_auth_provider_record = UserAuthProviderOrm(
        user_id=user_id,
        provider=provider,
        provider_subject=provider_subject or _build_unique_provider_subject(),
        email_at_provider=email_at_provider,
        deleted_at=deleted_at,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    db_session.add(user_auth_provider_record)
    await db_session.flush()
    return user_auth_provider_record


def build_find_or_create_user_from_auth_provider_input(
    *,
    provider_subject: str | None = None,
    email: str | None = None,
    is_email_verified: bool = True,
    display_name: str | None = "Ada Lovelace",
    avatar_url: str | None = None,
) -> FindOrCreateUserFromAuthProviderInput:
    return FindOrCreateUserFromAuthProviderInput(
        provider=AuthProviderType.GOOGLE,
        provider_subject=provider_subject or _build_unique_provider_subject(),
        email=email or _build_unique_email(),
        is_email_verified=is_email_verified,
        display_name=display_name,
        avatar_url=avatar_url,
    )


def _build_unique_email() -> str:
    return f"user-{uuid4().hex}@example.com"


def _build_unique_provider_subject() -> str:
    return f"provider-subject-{uuid4().hex}"
