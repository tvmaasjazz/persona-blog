from pydantic import BaseModel


class PersonaInput(BaseModel):
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
