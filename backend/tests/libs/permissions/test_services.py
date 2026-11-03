import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.permissions.results import FindRolePermissionListResult
from libs.permissions.services import PermissionService
from libs.permissions.types import PermissionType, RoleType


@pytest.mark.parametrize("role", [RoleType.ADMIN, RoleType.CREATOR])
async def test_find_role_permission_list_full_access_role_returns_all_permissions(
    db_session: AsyncSession, role: RoleType
) -> None:
    permission_service = PermissionService(db_session=db_session)

    find_role_permission_list_result = await permission_service.find_role_permission_list(role)

    assert sorted(find_role_permission_list_result.permissions) == [
        PermissionType.BLOG_POST_READ,
        PermissionType.BLOG_POST_WRITE,
        PermissionType.GENERATE_TEXT_RUN_READ,
        PermissionType.GENERATE_TEXT_RUN_WRITE,
        PermissionType.PERSONA_READ,
        PermissionType.PERSONA_WRITE,
    ]


async def test_find_role_permission_list_reader_returns_only_reads(
    db_session: AsyncSession,
) -> None:
    permission_service = PermissionService(db_session=db_session)

    find_role_permission_list_result = await permission_service.find_role_permission_list(
        RoleType.READER
    )

    assert sorted(find_role_permission_list_result.permissions) == [
        PermissionType.BLOG_POST_READ,
        PermissionType.PERSONA_READ,
    ]


async def test_find_role_permission_list_system_returns_empty_list(
    db_session: AsyncSession,
) -> None:
    permission_service = PermissionService(db_session=db_session)

    find_role_permission_list_result = await permission_service.find_role_permission_list(
        RoleType.SYSTEM
    )

    assert find_role_permission_list_result == FindRolePermissionListResult(permissions=[])
