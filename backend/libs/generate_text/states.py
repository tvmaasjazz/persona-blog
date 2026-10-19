from uuid import UUID

from pydantic import BaseModel, field_validator

from libs.auth.results import AuthUser
from libs.generate_text.inputs import GenerateTextPersonaInput


class GenerateTextState(BaseModel):
    # Primitives only: the state is persisted in checkpoints
    auth_user_id: int
    auth_user_identity: UUID
    generate_text_run_id: int
    generate_text_run_identity: UUID
    graph_version: str
    text_type: str
    prompt_text: str
    persona_name: str
    persona_bio: str
    persona_background: str | None = None
    persona_writing_style: str | None = None
    persona_sample_writing: str | None = None
    tone: str | None = None
    target_audience: str | None = None
    additional_context: str | None = None
    step_outputs: dict[str, str] = {}
    step_decisions: dict[str, str] = {}
    step_feedback: dict[str, str] = {}
    rewrite_counts: dict[str, int] = {}
    current_step_id: int | None = None

    @field_validator("auth_user_identity", "generate_text_run_identity", mode="after")
    @classmethod
    def _coerce_plain_uuid(cls, identity: UUID) -> UUID:
        # asyncpg returns a UUID subclass that checkpoints as an unregistered type
        return identity if type(identity) is UUID else UUID(str(identity))

    def build_auth_user(self) -> AuthUser:
        return AuthUser(id=self.auth_user_id, identity=self.auth_user_identity)

    def build_persona(self) -> GenerateTextPersonaInput:
        return GenerateTextPersonaInput(
            name=self.persona_name,
            bio=self.persona_bio,
            background=self.persona_background,
            writing_style=self.persona_writing_style,
            sample_writing=self.persona_sample_writing,
        )

    def latest_output(self) -> str:
        """Returns the newest step output, or "" before any step has run."""
        if not self.step_outputs:
            return ""
        return next(reversed(self.step_outputs.values()))
