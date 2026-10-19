from typing import Annotated
from uuid import UUID

from fastapi import Depends

from apps.api.core.dependencies import AuthUserDep, DbSessionDep
from apps.api.domains.personas.dtos import PersonaDto
from libs.personas.services import PersonaService, PersonaValidationService


def get_persona_service(db_session: DbSessionDep) -> PersonaService:
    return PersonaService(db_session=db_session)


PersonaServiceDep = Annotated[PersonaService, Depends(get_persona_service)]


def get_persona_validation_service(db_session: DbSessionDep) -> PersonaValidationService:
    return PersonaValidationService(db_session=db_session)


PersonaValidationServiceDep = Annotated[
    PersonaValidationService, Depends(get_persona_validation_service)
]


async def validate_new_persona_name(
    dto: PersonaDto,
    auth_user: AuthUserDep,
    persona_validation_service: PersonaValidationServiceDep,
) -> None:
    """Rejects a new persona whose name the user already uses on another persona."""
    await persona_validation_service.validate_persona_name_available(dto.name, auth_user)


async def validate_renamed_persona_name(
    persona_identity: UUID,
    dto: PersonaDto,
    auth_user: AuthUserDep,
    persona_validation_service: PersonaValidationServiceDep,
) -> None:
    """Rejects a rename to a name the user already uses on a different persona."""
    await persona_validation_service.validate_persona_name_available(
        dto.name, auth_user, persona_identity
    )
