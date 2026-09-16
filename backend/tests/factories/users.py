from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import UserOrm


async def insert_user_row(
    db_session: AsyncSession,
    *,
    email: str | None = None,
    display_name: str | None = "Ada Lovelace",
    last_login_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> UserOrm:
    user_orm = UserOrm(
        email=email or _build_unique_email(),
        display_name=display_name,
        last_login_at=last_login_at,
        deleted_at=deleted_at,
    )
    db_session.add(user_orm)
    await db_session.flush()
    return user_orm


def _build_unique_email() -> str:
    return f"user-{uuid4().hex}@example.com"
