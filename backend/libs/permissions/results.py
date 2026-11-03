from pydantic import BaseModel

from libs.permissions.types import PermissionType


class FindRolePermissionListResult(BaseModel):
    permissions: list[PermissionType]
