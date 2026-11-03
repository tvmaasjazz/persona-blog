from typing import Annotated

from fastapi import Depends

from apps.api.core.dependencies import AppSettingsDep, DbSessionDep
from libs.users.services import UserService


def get_user_service(db_session: DbSessionDep, app_settings: AppSettingsDep) -> UserService:
    return UserService(
        db_session=db_session,
        low_credit_balance_threshold_usd=app_settings.credits.low_balance_threshold_usd,
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
