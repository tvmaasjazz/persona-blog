from typing import Annotated

from fastapi import Depends

from apps.api.core.dependencies import DbSessionDep
from libs.users.services import UserService


def get_user_service(db_session: DbSessionDep) -> UserService:
    return UserService(db_session=db_session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
