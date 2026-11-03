from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import PermissionOrm, RoleOrm, RolePermissionOrm
from libs.permissions.results import FindRolePermissionListResult
from libs.permissions.types import RoleType


class PermissionService:
    """Reads which permissions each role holds."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def find_role_permission_list(self, role: RoleType) -> FindRolePermissionListResult:
        """The permissions the role holds, empty when it holds none."""
        permission_query = (
            select(PermissionOrm.code)
            .join(RolePermissionOrm, RolePermissionOrm.permission_id == PermissionOrm.id)
            .join(RoleOrm, RoleOrm.id == RolePermissionOrm.role_id)
            .where(RoleOrm.code == role)
        )
        permission_query_result = await self._db_session.execute(permission_query)
        permission_codes = permission_query_result.scalars().all()

        return FindRolePermissionListResult(permissions=list(permission_codes))
