from typing import Annotated
from uuid import UUID

from fastapi import Depends

from apps.api.core.dependencies import AuthUserDep, DbTransactionDep
from apps.api.domains.personas.dtos import PersonaDto
from libs.personas.services import PersonaService


def get_persona_service(db_session: DbTransactionDep) -> PersonaService:
    return PersonaService(db_session=db_session)


PersonaServiceDep = Annotated[PersonaService, Depends(get_persona_service)]


async def ensure_new_persona_name_available(
    dto: PersonaDto,
    auth_user: AuthUserDep,
    persona_service: PersonaServiceDep,
) -> None:
    await persona_service.ensure_persona_name_available(dto.name, auth_user)


async def ensure_renamed_persona_name_available(
    persona_identity: UUID,
    dto: PersonaDto,
    auth_user: AuthUserDep,
    persona_service: PersonaServiceDep,
) -> None:
    await persona_service.ensure_persona_name_available(dto.name, auth_user, persona_identity)
