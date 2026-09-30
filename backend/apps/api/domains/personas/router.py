from uuid import UUID

from fastapi import APIRouter, Depends

from apps.api.core.dependencies import AuthUserDep
from apps.api.core.dtos import EmptyResponseDto, IdentityResponseDto
from apps.api.domains.personas.dependencies import (
    PersonaServiceDep,
    ensure_new_persona_name_available,
    ensure_renamed_persona_name_available,
)
from apps.api.domains.personas.dtos import (
    ListPersonasResponseDto,
    PersonaDto,
    PersonaResponseDto,
)

persona_router = APIRouter(prefix="/personas", tags=["personas"])


@persona_router.post("", status_code=201, dependencies=[Depends(ensure_new_persona_name_available)])
async def create_persona(
    dto: PersonaDto, auth_user: AuthUserDep, persona_service: PersonaServiceDep
) -> IdentityResponseDto:
    create_persona_result = await persona_service.create_persona(dto.to_input(), auth_user)
    return IdentityResponseDto(identity=create_persona_result.identity)


@persona_router.get("")
async def list_personas(
    auth_user: AuthUserDep, persona_service: PersonaServiceDep
) -> ListPersonasResponseDto:
    list_personas_result = await persona_service.list_personas(auth_user)
    return ListPersonasResponseDto.from_result(list_personas_result)


@persona_router.get("/{persona_identity}")
async def find_persona(
    persona_identity: UUID, auth_user: AuthUserDep, persona_service: PersonaServiceDep
) -> PersonaResponseDto:
    find_persona_result = await persona_service.find_persona(persona_identity, auth_user)
    return PersonaResponseDto.from_result(find_persona_result)


@persona_router.put(
    "/{persona_identity}", dependencies=[Depends(ensure_renamed_persona_name_available)]
)
async def update_persona(
    persona_identity: UUID,
    dto: PersonaDto,
    auth_user: AuthUserDep,
    persona_service: PersonaServiceDep,
) -> EmptyResponseDto:
    await persona_service.update_persona(persona_identity, dto.to_input(), auth_user)
    return EmptyResponseDto()


@persona_router.delete("/{persona_identity}")
async def delete_persona(
    persona_identity: UUID, auth_user: AuthUserDep, persona_service: PersonaServiceDep
) -> EmptyResponseDto:
    await persona_service.delete_persona(persona_identity, auth_user)
    return EmptyResponseDto()
