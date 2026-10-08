from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from libs.personas.inputs import PersonaInput
from libs.personas.results import FindUserPersonaListResult, PersonaDetailResult

PersonaNameStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
PersonaBioStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
AvatarUrlStr = Annotated[str, StringConstraints(max_length=2048, pattern=r"^https?://")]
PersonaShortTextStr = Annotated[str, StringConstraints(max_length=200)]
PersonaLongTextStr = Annotated[str, StringConstraints(max_length=2000)]
SampleWritingStr = Annotated[str, StringConstraints(max_length=10000)]


class PersonaDto(BaseModel):
    name: PersonaNameStr
    bio: PersonaBioStr
    avatar_url: AvatarUrlStr | None = None
    background: PersonaLongTextStr | None = None
    writing_style: PersonaLongTextStr | None = None
    default_tone: PersonaShortTextStr | None = None
    default_target_audience: PersonaShortTextStr | None = None
    sample_writing: SampleWritingStr | None = None
    is_public: bool = False

    def to_input(self) -> PersonaInput:
        return PersonaInput(
            name=self.name,
            bio=self.bio,
            avatar_url=self.avatar_url,
            background=self.background,
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
            writing_style=persona_detail_result.writing_style,
            default_tone=persona_detail_result.default_tone,
            default_target_audience=persona_detail_result.default_target_audience,
            sample_writing=persona_detail_result.sample_writing,
            is_public=persona_detail_result.is_public,
            created_at=persona_detail_result.created_at,
            updated_at=persona_detail_result.updated_at,
        )


class PersonaListResponseDto(BaseModel):
    personas: list[PersonaResponseDto]

    @classmethod
    def from_result(
        cls, find_user_persona_list_result: FindUserPersonaListResult
    ) -> PersonaListResponseDto:
        return cls(
            personas=[
                PersonaResponseDto.from_result(persona_detail_result)
                for persona_detail_result in find_user_persona_list_result.personas
            ]
        )
