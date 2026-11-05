from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.admin.exceptions import AdminUserNotChangeableException
from libs.admin.inputs import AdminSetUserActiveInput, AdminSetUserRoleInput
from libs.admin.results import (
    AdminFindUserListResult,
    AdminSetUserActiveResult,
    AdminSetUserRoleResult,
    AdminUserDetailResult,
)
from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm import RoleOrm, UserOrm
from libs.permissions.types import RoleType


class AdminUserService:
    """Reads any user's account and sets their role or suspension for the admin, skipping the
    ownership checks other services make; the system user is never shown."""

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

    async def set_user_role(
        self,
        user_identity: UUID,
        admin_set_user_role_input: AdminSetUserRoleInput,
        auth_user: AuthUser,
    ) -> AdminSetUserRoleResult:
        """Sets the user's role, saying whether it changed and whether a creator became a
        reader; NotFoundException for an unknown identity or the system user,
        AdminUserNotChangeableException for an admin."""
        # Find the user, refusing an admin
        user_id, current_role, _ = await self._find_changeable_user(user_identity)

        # Leave a user who already has the role
        if current_role == admin_set_user_role_input.role:
            return AdminSetUserRoleResult(
                user_id=user_id, is_changed=False, is_demoted_to_reader=False
            )

        # Set the role
        role_id_query = select(RoleOrm.id).where(RoleOrm.code == admin_set_user_role_input.role)
        user_role_update = (
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(role_id=role_id_query.scalar_subquery(), updated_by_id=auth_user.id)
        )
        await self._db_session.execute(user_role_update)

        is_demoted_to_reader = (
            current_role == RoleType.CREATOR and admin_set_user_role_input.role == RoleType.READER
        )
        return AdminSetUserRoleResult(
            user_id=user_id, is_changed=True, is_demoted_to_reader=is_demoted_to_reader
        )

    async def set_user_active(
        self,
        user_identity: UUID,
        admin_set_user_active_input: AdminSetUserActiveInput,
        auth_user: AuthUser,
    ) -> AdminSetUserActiveResult:
        """Suspends or reactivates the user, saying whether it changed; NotFoundException for
        an unknown identity or the system user, AdminUserNotChangeableException for an
        admin."""
        # Find the user, refusing an admin
        user_id, _, is_active = await self._find_changeable_user(user_identity)

        # Leave a user who already has the state
        if is_active == admin_set_user_active_input.is_active:
            return AdminSetUserActiveResult(user_id=user_id, is_changed=False)

        # Set the state
        user_active_update = (
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(is_active=admin_set_user_active_input.is_active, updated_by_id=auth_user.id)
        )
        await self._db_session.execute(user_active_update)

        return AdminSetUserActiveResult(user_id=user_id, is_changed=True)

    async def _find_changeable_user(self, user_identity: UUID) -> tuple[int, RoleType, bool]:
        """The user's id, role and is_active; refuses the system user and an admin."""
        user_query = (
            select(UserOrm.id, RoleOrm.code, UserOrm.is_active)
            .join(RoleOrm, RoleOrm.id == UserOrm.role_id)
            .where(UserOrm.identity == user_identity, UserOrm.is_system_user.is_(False))
        )
        user_query_result = await self._db_session.execute(user_query)
        user_row = user_query_result.one_or_none()

        if user_row is None:
            raise NotFoundException("User not found")
        user_id, role, is_active = user_row
        if role == RoleType.ADMIN:
            raise AdminUserNotChangeableException("An admin's role and access can't be changed")
        return user_id, role, is_active

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
