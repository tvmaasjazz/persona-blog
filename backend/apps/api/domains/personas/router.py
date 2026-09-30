from uuid import UUID

from fastapi import APIRouter, Depends

from apps.api.core.dependencies import AuthUserDep
from apps.api.core.dtos import EmptyResponseDto, IdentityResponseDto
from apps.api.domains.personas.dependencies import (
    PersonaServiceDep,
    validate_new_persona_name,
    validate_renamed_persona_name,
)
from apps.api.domains.personas.dtos import (
    PersonaDto,
    PersonaListResponseDto,
    PersonaResponseDto,
)

persona_router = APIRouter(prefix="/personas", tags=["personas"])


@persona_router.get("")
async def find_user_persona_list(
    auth_user: AuthUserDep, persona_service: PersonaServiceDep
) -> PersonaListResponseDto:
    find_user_persona_list_result = await persona_service.find_user_persona_list(auth_user)
    return PersonaListResponseDto.from_result(find_user_persona_list_result)


@persona_router.get("/{persona_identity}")
async def find_persona(
    persona_identity: UUID, auth_user: AuthUserDep, persona_service: PersonaServiceDep
) -> PersonaResponseDto:
    find_persona_result = await persona_service.find_persona(persona_identity, auth_user)
    return PersonaResponseDto.from_result(find_persona_result)


@persona_router.post("", status_code=201, dependencies=[Depends(validate_new_persona_name)])
async def create_persona(
    dto: PersonaDto, auth_user: AuthUserDep, persona_service: PersonaServiceDep
) -> IdentityResponseDto:
    create_persona_result = await persona_service.create_persona(dto.to_input(), auth_user)
    return IdentityResponseDto(identity=create_persona_result.identity)


@persona_router.put("/{persona_identity}", dependencies=[Depends(validate_renamed_persona_name)])
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
