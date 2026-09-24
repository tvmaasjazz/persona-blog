from uuid import UUID

from fastapi import APIRouter

from apps.api.core.dependencies import AuthUserDep
from apps.api.domains.generate_text.dependencies import GenerateTextServiceDep
from apps.api.domains.generate_text.dtos import (
    GeneratedTextResponseDto,
    GenerateTextDto,
    ResumeGenerateTextDto,
)

generate_text_router = APIRouter(prefix="/generate-text", tags=["generate-text"])


@generate_text_router.post("/")
async def generate_text(
    dto: GenerateTextDto,
    auth_user: AuthUserDep,
    generate_text_service: GenerateTextServiceDep,
) -> GeneratedTextResponseDto:
    generate_text_result = await generate_text_service.generate_text(dto.to_input(), auth_user)
    return GeneratedTextResponseDto.from_result(generate_text_result)


@generate_text_router.post("/{thread_identity}/resume")
async def resume_generate_text(
    thread_identity: UUID,
    dto: ResumeGenerateTextDto,
    auth_user: AuthUserDep,
    generate_text_service: GenerateTextServiceDep,
) -> GeneratedTextResponseDto:
    resume_generate_text_result = await generate_text_service.resume_generate_text(
        thread_identity, dto.to_input(), auth_user
    )
    return GeneratedTextResponseDto.from_result(resume_generate_text_result)
