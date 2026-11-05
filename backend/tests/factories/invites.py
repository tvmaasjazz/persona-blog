from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import InviteOrm
from libs.invites.utils import InviteUtils
from libs.permissions.types import RoleType
from tests.factories.users import insert_user_row


async def insert_invite_row(
    db_session: AsyncSession,
    *,
    name: str = "Ada's invite",
    credit_amount_usd: Decimal = Decimal("5.00"),
    note: str | None = None,
    code_hash: str | None = None,
    expires_at: datetime = datetime(2099, 1, 1, tzinfo=UTC),
    used_at: datetime | None = None,
    used_by_user_id: int | None = None,
    revoked_at: datetime | None = None,
    created_by_id: int | None = None,
    created_at: datetime | None = None,
) -> InviteOrm:
    # An invite is made by an admin, so one is inserted unless the test names the author
    if created_by_id is None:
        admin_record = await insert_user_row(db_session, role=RoleType.ADMIN)
        author_id = admin_record.id
    else:
        author_id = created_by_id
    invite_record = InviteOrm(
        name=name,
        credit_amount_usd=credit_amount_usd,
        note=note,
        code_hash=code_hash or InviteUtils.hash_code(f"code-{uuid4().hex}"),
        expires_at=expires_at,
        used_at=used_at,
        used_by_user_id=used_by_user_id,
        revoked_at=revoked_at,
        created_by_id=author_id,
        updated_by_id=author_id,
    )
    # Left unset, the column's default fills it in
    if created_at is not None:
        invite_record.created_at = created_at
    db_session.add(invite_record)
    await db_session.flush()
    return invite_record
