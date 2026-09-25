from uuid import UUID

from fastapi import APIRouter

from apps.api.core.dependencies import AuthUserDep, GenerateTextServiceDep
from apps.api.domains.generate_text_runs.dtos import (
    GenerateTextRunResponseDto,
    ResumeGenerateTextDto,
)

generate_text_run_router = APIRouter(prefix="/generate-text-runs", tags=["generate-text-runs"])


@generate_text_run_router.get("/{run_identity}")
async def find_generate_text_run(
    run_identity: UUID, auth_user: AuthUserDep, generate_text_service: GenerateTextServiceDep
) -> GenerateTextRunResponseDto:
    find_generate_text_run_result = await generate_text_service.find_generate_text_run(
        run_identity, auth_user
    )
    return GenerateTextRunResponseDto.from_result(find_generate_text_run_result)


@generate_text_run_router.post("/{run_identity}/resume")
async def resume_generate_text(
    run_identity: UUID,
    dto: ResumeGenerateTextDto,
    auth_user: AuthUserDep,
    generate_text_service: GenerateTextServiceDep,
) -> GenerateTextRunResponseDto:
    resume_generate_text_result = await generate_text_service.resume_generate_text(
        run_identity, dto.to_input(), auth_user
    )
    return GenerateTextRunResponseDto.from_result(resume_generate_text_result)
