from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from apps.api.core.dtos import BasePageQueryDto, BasePageResponseDto, PaginationResponseDto
from libs.personas.inputs import FindUserPersonaPageInput, PersonaInput
from libs.personas.results import (
    FindUserPersonaPageResult,
    PersonaDetailResult,
    PublicPersonaResult,
)
from libs.personas.types import UserPersonaSortType

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


class PublicPersonaResponseDto(BaseModel):
    identity: UUID
    name: str
    bio: str
    avatar_url: str | None
    is_public: bool
    is_owner: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_result(cls, public_persona_result: PublicPersonaResult) -> PublicPersonaResponseDto:
        return cls(
            identity=public_persona_result.identity,
            name=public_persona_result.name,
            bio=public_persona_result.bio,
            avatar_url=public_persona_result.avatar_url,
            is_public=public_persona_result.is_public,
            is_owner=public_persona_result.is_owner,
            created_at=public_persona_result.created_at,
            updated_at=public_persona_result.updated_at,
        )


class UserPersonaPageQueryDto(BasePageQueryDto):
    sort_by: UserPersonaSortType = UserPersonaSortType.CREATED_AT

    def to_input(self) -> FindUserPersonaPageInput:
        return FindUserPersonaPageInput(
            pagination_input=self.to_pagination_input(), sort_by=self.sort_by
        )


class UserPersonaPageResponseDto(BasePageResponseDto):
    personas: list[PersonaResponseDto]

    @classmethod
    def from_result(
        cls, find_user_persona_page_result: FindUserPersonaPageResult
    ) -> UserPersonaPageResponseDto:
        return cls(
            personas=[
                PersonaResponseDto.from_result(persona_detail_result)
                for persona_detail_result in find_user_persona_page_result.personas
            ],
            pagination=PaginationResponseDto.from_result(find_user_persona_page_result.pagination),
        )
