from fastapi import APIRouter

from apps.api.domains.invites.dependencies import InviteServiceDep
from apps.api.domains.invites.dtos import CheckInviteDto, InviteStatusResponseDto

invite_router = APIRouter(prefix="/invites", tags=["invites"])


@invite_router.post("/check")
async def find_invite_status(
    dto: CheckInviteDto, invite_service: InviteServiceDep
) -> InviteStatusResponseDto:
    """Returns an invite code's status and credit amount, open to anyone holding the code;
    404 for an unknown code."""
    find_invite_status_result = await invite_service.find_invite_status(dto.code)
    return InviteStatusResponseDto.from_result(find_invite_status_result)
