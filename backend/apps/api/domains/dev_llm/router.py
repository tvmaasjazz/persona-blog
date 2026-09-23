from fastapi import APIRouter

from apps.api.core.dependencies import AuthUserDep, LlmServiceDep
from apps.api.domains.dev_llm.dtos import CompleteLlmDto, LlmCompletionResponseDto

dev_llm_router = APIRouter(prefix="/dev/llm", tags=["dev-llm"])


@dev_llm_router.post("/complete")
async def complete_llm(
    dto: CompleteLlmDto,
    auth_user: AuthUserDep,
    llm_service: LlmServiceDep,
) -> LlmCompletionResponseDto:
    complete_result = await llm_service.complete(dto.to_input(), auth_user)
    return LlmCompletionResponseDto.from_result(complete_result)
