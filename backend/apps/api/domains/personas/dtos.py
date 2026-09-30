from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from libs.personas.inputs import PersonaInput
from libs.personas.results import ListPersonasResult, PersonaDetailResult


class PersonaDto(BaseModel):
    name: str
    bio: str
    avatar_url: str | None = None
    background: str | None = None
    expertise: str | None = None
    writing_style: str | None = None
    default_tone: str | None = None
    default_target_audience: str | None = None
    sample_writing: str | None = None
    is_public: bool = False

    def to_input(self) -> PersonaInput:
        return PersonaInput(
            name=self.name,
            bio=self.bio,
            avatar_url=self.avatar_url,
            background=self.background,
            expertise=self.expertise,
            writing_style=self.writing_style,
            default_tone=self.default_tone,
            default_target_audience=self.default_target_audience,
            sample_writing=self.sample_writing,
            is_public=self.is_public,
        )


class PersonaResponseDto(BaseModel):
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

    @classmethod
    def from_result(cls, persona_detail_result: PersonaDetailResult) -> PersonaResponseDto:
        return cls(
            identity=persona_detail_result.identity,
            name=persona_detail_result.name,
            bio=persona_detail_result.bio,
            avatar_url=persona_detail_result.avatar_url,
            background=persona_detail_result.background,
            expertise=persona_detail_result.expertise,
            writing_style=persona_detail_result.writing_style,
            default_tone=persona_detail_result.default_tone,
            default_target_audience=persona_detail_result.default_target_audience,
            sample_writing=persona_detail_result.sample_writing,
            is_public=persona_detail_result.is_public,
            created_at=persona_detail_result.created_at,
            updated_at=persona_detail_result.updated_at,
        )


class ListPersonasResponseDto(BaseModel):
    personas: list[PersonaResponseDto]

    @classmethod
    def from_result(cls, list_personas_result: ListPersonasResult) -> ListPersonasResponseDto:
        return cls(
            personas=[
                PersonaResponseDto.from_result(persona_detail_result)
                for persona_detail_result in list_personas_result.personas
            ]
        )
