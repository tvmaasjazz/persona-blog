from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import AuthUserDep, require_permissions
from apps.api.core.dtos import EmptyResponseDto, IdentityResponseDto
from apps.api.domains.admin.dependencies import (
    AdminCreditServiceDep,
    AdminInviteServiceDep,
    AdminUserServiceDep,
)
from apps.api.domains.admin.dtos import (
    AdminCreditGrantDto,
    AdminCreditLedgerResponseDto,
    AdminInviteCreateResponseDto,
    AdminInviteDto,
    AdminInviteListResponseDto,
    AdminUserActiveDto,
    AdminUserListResponseDto,
    AdminUserResponseDto,
    AdminUserRoleDto,
)
from libs.auth.after_response_tasks import delete_user_sessions
from libs.generate_text.after_response_tasks import fail_user_unfinished_runs
from libs.generate_text.constants import (
    USER_ROLE_CHANGED_ERROR_CODE,
    USER_ROLE_CHANGED_ERROR_MESSAGE,
    USER_SUSPENDED_ERROR_CODE,
    USER_SUSPENDED_ERROR_MESSAGE,
)
from libs.permissions.types import PermissionType

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get(
    "/users",
    dependencies=[Depends(require_permissions(PermissionType.USER_READ))],
)
async def find_user_list(admin_user_service: AdminUserServiceDep) -> AdminUserListResponseDto:
    """Lists every user, newest first, with their role and balance."""
    find_user_list_result = await admin_user_service.find_user_list()
    return AdminUserListResponseDto.from_result(find_user_list_result)


@admin_router.get(
    "/users/{user_identity}",
    dependencies=[Depends(require_permissions(PermissionType.USER_READ))],
)
async def find_user(
    user_identity: UUID, admin_user_service: AdminUserServiceDep
) -> AdminUserResponseDto:
    """Returns one user with their role and balance; 404 for an unknown user."""
    admin_user_detail_result = await admin_user_service.find_user(user_identity)
    return AdminUserResponseDto.from_result(admin_user_detail_result)


@admin_router.get(
    "/users/{user_identity}/credit-ledger",
    dependencies=[Depends(require_permissions(PermissionType.CREDIT_READ))],
)
async def find_user_credit_ledger(
    user_identity: UUID, admin_credit_service: AdminCreditServiceDep
) -> AdminCreditLedgerResponseDto:
    """Lists the user's credit ledger, newest first; 404 for an unknown user."""
    find_user_credit_ledger_result = await admin_credit_service.find_user_credit_ledger(
        user_identity
    )
    return AdminCreditLedgerResponseDto.from_result(find_user_credit_ledger_result)


@admin_router.post(
    "/users/{user_identity}/credit-grants",
    status_code=201,
    dependencies=[Depends(require_permissions(PermissionType.CREDIT_WRITE))],
)
async def grant_user_credits(
    user_identity: UUID,
    dto: AdminCreditGrantDto,
    request: Request,
    after_response_tasks: BackgroundTasks,
    auth_user: AuthUserDep,
    admin_credit_service: AdminCreditServiceDep,
) -> IdentityResponseDto:
    """Grants the user credits and makes a reader a creator, signing them out everywhere so
    they sign in with the new role; 404 for an unknown user, 409 for the system user."""
    grant_user_credits_result = await admin_credit_service.grant_user_credits(
        user_identity, dto.to_input(), auth_user
    )

    # Sign a new creator out after the response, once the role change has committed
    if grant_user_credits_result.is_made_creator:
        app_settings: AppSettings = request.app.state.settings
        after_response_tasks.add_task(
            delete_user_sessions,
            redis_client=request.app.state.redis_client,
            auth_settings=app_settings.auth,
            user_id=grant_user_credits_result.user_id,
        )
    return IdentityResponseDto(identity=grant_user_credits_result.identity)


@admin_router.get(
    "/invites",
    dependencies=[Depends(require_permissions(PermissionType.INVITE_READ))],
)
async def find_invite_list(
    admin_invite_service: AdminInviteServiceDep,
) -> AdminInviteListResponseDto:
    """Lists every invite, newest first, with its status and who used it."""
    find_invite_list_result = await admin_invite_service.find_invite_list()
    return AdminInviteListResponseDto.from_result(find_invite_list_result)


@admin_router.post(
    "/invites",
    status_code=201,
    dependencies=[Depends(require_permissions(PermissionType.INVITE_WRITE))],
)
async def create_invite(
    dto: AdminInviteDto, auth_user: AuthUserDep, admin_invite_service: AdminInviteServiceDep
) -> AdminInviteCreateResponseDto:
    """Creates an invite and returns its identity and link; the link is the only time the
    code is shown."""
    create_invite_result = await admin_invite_service.create_invite(dto.to_input(), auth_user)
    return AdminInviteCreateResponseDto.from_result(create_invite_result)


@admin_router.post(
    "/invites/{invite_identity}/revoke",
    dependencies=[Depends(require_permissions(PermissionType.INVITE_WRITE))],
)
async def revoke_invite(
    invite_identity: UUID, auth_user: AuthUserDep, admin_invite_service: AdminInviteServiceDep
) -> EmptyResponseDto:
    """Revokes an unused invite; 404 for an unknown invite, 409 for a used one."""
    await admin_invite_service.revoke_invite(invite_identity, auth_user)
    return EmptyResponseDto()


@admin_router.put(
    "/users/{user_identity}/role",
    dependencies=[Depends(require_permissions(PermissionType.USER_WRITE))],
)
async def set_user_role(
    user_identity: UUID,
    dto: AdminUserRoleDto,
    request: Request,
    after_response_tasks: BackgroundTasks,
    auth_user: AuthUserDep,
    admin_user_service: AdminUserServiceDep,
) -> EmptyResponseDto:
    """Sets the user's role to reader or creator, signing them out everywhere and, when a
    creator becomes a reader, failing their unfinished runs; 404 for an unknown user, 409
    for an admin."""
    set_user_role_result = await admin_user_service.set_user_role(
        user_identity, dto.to_input(), auth_user
    )

    # Sign the user out after the response, once the change has committed
    if set_user_role_result.is_changed:
        app_settings: AppSettings = request.app.state.settings
        after_response_tasks.add_task(
            delete_user_sessions,
            redis_client=request.app.state.redis_client,
            auth_settings=app_settings.auth,
            user_id=set_user_role_result.user_id,
        )

    # A reader can't generate text, so what the user had running stops
    if set_user_role_result.is_demoted_to_reader:
        after_response_tasks.add_task(
            fail_user_unfinished_runs,
            db_session_factory=request.app.state.db_session_factory,
            user_id=set_user_role_result.user_id,
            error_code=USER_ROLE_CHANGED_ERROR_CODE,
            error_message=USER_ROLE_CHANGED_ERROR_MESSAGE,
        )
    return EmptyResponseDto()


@admin_router.put(
    "/users/{user_identity}/active",
    dependencies=[Depends(require_permissions(PermissionType.USER_WRITE))],
)
async def set_user_active(
    user_identity: UUID,
    dto: AdminUserActiveDto,
    request: Request,
    after_response_tasks: BackgroundTasks,
    auth_user: AuthUserDep,
    admin_user_service: AdminUserServiceDep,
) -> EmptyResponseDto:
    """Suspends or reactivates the user; a suspension signs them out everywhere and fails
    their unfinished runs; 404 for an unknown user, 409 for an admin."""
    set_user_active_result = await admin_user_service.set_user_active(
        user_identity, dto.to_input(), auth_user
    )

    # Sign the user out after the response, once the change has committed
    if set_user_active_result.is_changed:
        app_settings: AppSettings = request.app.state.settings
        after_response_tasks.add_task(
            delete_user_sessions,
            redis_client=request.app.state.redis_client,
            auth_settings=app_settings.auth,
            user_id=set_user_active_result.user_id,
        )

    # A suspended user's runs stop
    if set_user_active_result.is_changed and not dto.is_active:
        after_response_tasks.add_task(
            fail_user_unfinished_runs,
            db_session_factory=request.app.state.db_session_factory,
            user_id=set_user_active_result.user_id,
            error_code=USER_SUSPENDED_ERROR_CODE,
            error_message=USER_SUSPENDED_ERROR_MESSAGE,
        )
    return EmptyResponseDto()
