from typing import Annotated

from fastapi import Depends

from apps.api.core.dependencies import AppSettingsDep, DbSessionDep
from apps.api.domains.blog_posts.dependencies import PaginationServiceDep
from apps.api.domains.users.dependencies import UserServiceDep
from libs.admin.services import AdminCreditService, AdminInviteService, AdminUserService
from libs.credits.services import CreditLedgerService


def get_admin_user_service(
    db_session: DbSessionDep, pagination_service: PaginationServiceDep
) -> AdminUserService:
    return AdminUserService(db_session=db_session, pagination_service=pagination_service)


AdminUserServiceDep = Annotated[AdminUserService, Depends(get_admin_user_service)]


def get_credit_ledger_service(db_session: DbSessionDep) -> CreditLedgerService:
    return CreditLedgerService(db_session=db_session)


CreditLedgerServiceDep = Annotated[CreditLedgerService, Depends(get_credit_ledger_service)]


def get_admin_credit_service(
    db_session: DbSessionDep,
    credit_ledger_service: CreditLedgerServiceDep,
    user_service: UserServiceDep,
    pagination_service: PaginationServiceDep,
) -> AdminCreditService:
    return AdminCreditService(
        db_session=db_session,
        credit_ledger_service=credit_ledger_service,
        user_service=user_service,
        pagination_service=pagination_service,
    )


AdminCreditServiceDep = Annotated[AdminCreditService, Depends(get_admin_credit_service)]


def get_admin_invite_service(
    db_session: DbSessionDep,
    app_settings: AppSettingsDep,
    pagination_service: PaginationServiceDep,
) -> AdminInviteService:
    return AdminInviteService(
        db_session=db_session,
        frontend_url=app_settings.auth.frontend_url,
        pagination_service=pagination_service,
    )


AdminInviteServiceDep = Annotated[AdminInviteService, Depends(get_admin_invite_service)]
