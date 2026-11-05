from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.results import AdminFindUserListResult, AdminUserDetailResult
from libs.core.exceptions import NotFoundException
from libs.database.orm import RoleOrm, UserOrm


class AdminUserService:
    """Reads any user's account for the admin, skipping the ownership checks other services
    make; the system user is never shown."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def find_user_list(self) -> AdminFindUserListResult:
        """Every user but the system user, newest first, with their role and balance."""
        user_query = (
            self._build_admin_user_query()
            .where(UserOrm.is_system_user.is_(False))
            .order_by(UserOrm.created_at.desc(), UserOrm.id.desc())
        )
        user_query_result = await self._db_session.execute(user_query)
        user_rows = user_query_result.mappings().all()

        return AdminFindUserListResult(
            users=[AdminUserDetailResult.model_validate(user_row) for user_row in user_rows]
        )

    async def find_user(self, user_identity: UUID) -> AdminUserDetailResult:
        """The user with their role and balance; NotFoundException for an unknown identity or
        the system user."""
        user_query = self._build_admin_user_query().where(
            UserOrm.identity == user_identity, UserOrm.is_system_user.is_(False)
        )
        user_query_result = await self._db_session.execute(user_query)
        user_row = user_query_result.mappings().one_or_none()

        if user_row is None:
            raise NotFoundException("User not found")
        return AdminUserDetailResult.model_validate(user_row)

    def _build_admin_user_query(self) -> Select:
        return select(
            UserOrm.identity,
            UserOrm.email,
            UserOrm.display_name,
            RoleOrm.code.label("role"),
            UserOrm.credit_balance_usd,
            UserOrm.is_active,
            UserOrm.created_at,
            UserOrm.last_activity_at,
        ).join(RoleOrm, RoleOrm.id == UserOrm.role_id)
