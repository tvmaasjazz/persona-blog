from pydantic import BaseModel

from libs.core.inputs import BasePageInput
from libs.personas.types import UserPersonaSortType


class FindUserPersonaPageInput(BasePageInput):
    sort_by: UserPersonaSortType


class PersonaInput(BaseModel):
    name: str
    bio: str
    avatar_url: str | None
    background: str | None
    writing_style: str | None
    default_tone: str | None
    default_target_audience: str | None
    sample_writing: str | None
    is_public: bool
