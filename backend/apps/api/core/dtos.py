from uuid import UUID

from pydantic import BaseModel


class IdentityResponseDto(BaseModel):
    identity: UUID


class EmptyResponseDto(BaseModel):
    pass
