from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePersonaResult(BaseModel):
    identity: UUID


class PersonaDetailResult(BaseModel):
    """What a persona looks like to a caller, whether just read or listed.

    Shared by find_persona and list_personas."""

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


class ListPersonasResult(BaseModel):
    personas: list[PersonaDetailResult]
