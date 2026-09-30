from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePersonaResult(BaseModel):
    identity: UUID


class PersonaDetailResult(BaseModel):
    identity: UUID
    name: str
    bio: str
    avatar_url: str | None
    background: str | None
    expertise: str | None
    writing_style: str | None
    default_tone: str | None
    default_target_audience: str | None
    sample_writing: str | None
    is_public: bool
    created_at: datetime
    updated_at: datetime


class FindUserPersonaListResult(BaseModel):
    personas: list[PersonaDetailResult]


class FindUserPersonaResult(BaseModel):
    """The caller's own persona, including its id: the BIGINT foreign key another
    domain's write needs, which never leaves the backend."""

    id: int
    identity: UUID
    name: str
    bio: str
    background: str | None
    expertise: str | None
    writing_style: str | None
    sample_writing: str | None
