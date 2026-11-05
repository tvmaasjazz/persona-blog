from typing import Annotated

from fastapi import Depends

from apps.api.core.dependencies import DbSessionDep
from apps.api.domains.users.dependencies import UserServiceDep
from libs.credits.services import CreditLedgerService
from libs.invites.services import InviteService


def get_invite_service(db_session: DbSessionDep, user_service: UserServiceDep) -> InviteService:
    return InviteService(
        db_session=db_session,
        credit_ledger_service=CreditLedgerService(db_session=db_session),
        user_service=user_service,
    )


InviteServiceDep = Annotated[InviteService, Depends(get_invite_service)]
