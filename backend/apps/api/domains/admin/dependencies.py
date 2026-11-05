from typing import Annotated

from fastapi import Depends

from apps.api.core.dependencies import DbSessionDep
from libs.admin.services import AdminCreditService, AdminUserService
from libs.credits.services import CreditLedgerService


def get_admin_user_service(db_session: DbSessionDep) -> AdminUserService:
    return AdminUserService(db_session=db_session)


AdminUserServiceDep = Annotated[AdminUserService, Depends(get_admin_user_service)]


def get_credit_ledger_service(db_session: DbSessionDep) -> CreditLedgerService:
    return CreditLedgerService(db_session=db_session)


CreditLedgerServiceDep = Annotated[CreditLedgerService, Depends(get_credit_ledger_service)]


def get_admin_credit_service(
    db_session: DbSessionDep, credit_ledger_service: CreditLedgerServiceDep
) -> AdminCreditService:
    return AdminCreditService(db_session=db_session, credit_ledger_service=credit_ledger_service)


AdminCreditServiceDep = Annotated[AdminCreditService, Depends(get_admin_credit_service)]
