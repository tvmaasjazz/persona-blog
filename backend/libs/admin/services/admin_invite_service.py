from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from libs.admin.exceptions import AdminInviteUsedException
from libs.admin.inputs import AdminCreateInviteInput
from libs.admin.results import (
    AdminCreateInviteResult,
    AdminFindInviteListResult,
    AdminInviteDetailResult,
)
from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm import InviteOrm, UserOrm
from libs.database.utils import DatabaseClockUtils
from libs.invites.constants import SECONDS_PER_DAY
from libs.invites.utils import InviteUtils


class AdminInviteService:
    """Creates, lists and revokes invites for the admin; the invite's code is shown once, in
    the link a create returns."""

    def __init__(self, db_session: AsyncSession, frontend_url: str) -> None:
        self._db_session = db_session
        self._frontend_url = frontend_url

    async def create_invite(
        self, admin_create_invite_input: AdminCreateInviteInput, auth_user: AuthUser
    ) -> AdminCreateInviteResult:
        """Creates an invite storing only the code's hash, and returns its identity and link."""
        code = InviteUtils.build_code()
        expires_in_seconds = admin_create_invite_input.expires_in_days * SECONDS_PER_DAY
        invite_insert = (
            insert(InviteOrm)
            .values(
                name=admin_create_invite_input.name,
                credit_amount_usd=admin_create_invite_input.credit_amount_usd,
                note=admin_create_invite_input.note,
                code_hash=InviteUtils.hash_code(code),
                expires_at=DatabaseClockUtils.build_utc_now_plus_sql(expires_in_seconds),
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            .returning(InviteOrm.identity)
        )
        invite_insert_result = await self._db_session.execute(invite_insert)
        invite_identity = invite_insert_result.scalar_one()

        invite_url = InviteUtils.build_invite_url(self._frontend_url, code)
        return AdminCreateInviteResult(identity=invite_identity, invite_url=invite_url)

    async def find_invite_list(self) -> AdminFindInviteListResult:
        """Every invite, newest first, with its status and who used it."""
        used_by_user = aliased(UserOrm)
        created_by_user = aliased(UserOrm)
        invite_query = (
            select(
                InviteOrm.identity,
                InviteOrm.name,
                InviteOrm.credit_amount_usd,
                InviteOrm.note,
                InviteOrm.expires_at,
                InviteOrm.used_at,
                used_by_user.email.label("used_by_email"),
                InviteOrm.revoked_at,
                InviteOrm.created_at,
                created_by_user.email.label("created_by_email"),
                (InviteOrm.expires_at <= DatabaseClockUtils.build_utc_now_sql()).label(
                    "is_expired"
                ),
            )
            .outerjoin(used_by_user, used_by_user.id == InviteOrm.used_by_user_id)
            .join(created_by_user, created_by_user.id == InviteOrm.created_by_id)
            .order_by(InviteOrm.created_at.desc(), InviteOrm.id.desc())
        )
        invite_query_result = await self._db_session.execute(invite_query)
        invite_rows = invite_query_result.all()

        return AdminFindInviteListResult(
            invites=[
                AdminInviteDetailResult(
                    identity=invite_row.identity,
                    name=invite_row.name,
                    credit_amount_usd=invite_row.credit_amount_usd,
                    note=invite_row.note,
                    status=InviteUtils.build_status_type(
                        invite_row.revoked_at, invite_row.used_at, invite_row.is_expired
                    ),
                    expires_at=invite_row.expires_at,
                    used_at=invite_row.used_at,
                    used_by_email=invite_row.used_by_email,
                    revoked_at=invite_row.revoked_at,
                    created_at=invite_row.created_at,
                    created_by_email=invite_row.created_by_email,
                )
                for invite_row in invite_rows
            ]
        )

    async def revoke_invite(self, invite_identity: UUID, auth_user: AuthUser) -> None:
        """Revokes an unused invite, expired or not; a revoked one is left as it is,
        NotFoundException for an unknown identity, AdminInviteUsedException for a used one."""
        # Revoke an invite that is neither used nor already revoked
        invite_revoke_update = (
            update(InviteOrm)
            .where(
                InviteOrm.identity == invite_identity,
                InviteOrm.used_at.is_(None),
                InviteOrm.revoked_at.is_(None),
            )
            .values(
                revoked_at=DatabaseClockUtils.build_utc_now_sql(),
                updated_by_id=auth_user.id,
            )
        )
        invite_revoke_update_result = await self._db_session.execute(invite_revoke_update)
        if invite_revoke_update_result.rowcount == 1:
            return

        # Nothing changed: tell an unknown or used invite from one already revoked
        invite_query = select(InviteOrm.used_at).where(InviteOrm.identity == invite_identity)
        invite_query_result = await self._db_session.execute(invite_query)
        invite_row = invite_query_result.one_or_none()

        if invite_row is None:
            raise NotFoundException("Invite not found")
        if invite_row.used_at is not None:
            raise AdminInviteUsedException("A used invite can't be revoked")
