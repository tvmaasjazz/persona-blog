from uuid import UUID

from pydantic import BaseModel, field_validator

from libs.auth.results import AuthUser
from libs.generate_text.inputs import GenerateTextPersonaInput


class GenerateTextState(BaseModel):
    """The graph's state: the acting user, the run it belongs to, and every step's
    output, decision, and feedback so far.

    Every field is a primitive, because the state is a persisted wire format. A domain
    class here would tie old checkpoints to that class's import path, and LangGraph will
    refuse to deserialize unregistered types in a future version.
    """

    auth_user_id: int
    auth_user_identity: UUID
    generate_text_run_id: int
    generate_text_run_identity: UUID
    graph_version: str
    text_type: str
    prompt_text: str
    persona: dict[str, str | None] = {}
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
        """asyncpg returns its own UUID subclass. LangGraph would checkpoint that as an
        unregistered type, which a future version refuses to read back."""
        return identity if type(identity) is UUID else UUID(str(identity))

    def build_auth_user(self) -> AuthUser:
        """Groups the stored primitives back into the shape LlmService takes."""
        return AuthUser(id=self.auth_user_id, identity=self.auth_user_identity)

    def build_persona(self) -> GenerateTextPersonaInput:
        """Groups the stored persona dict back into the shape a Prompt takes."""
        return GenerateTextPersonaInput.model_validate(self.persona)

    def latest_output(self) -> str:
        """The most recently written step output, or "" before any step has run."""
        if not self.step_outputs:
            return ""
        return next(reversed(self.step_outputs.values()))
