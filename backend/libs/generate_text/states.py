from uuid import UUID

from pydantic import BaseModel

from libs.auth.results import AuthUser


class GenerateTextState(BaseModel):
    """The graph's state: the acting user, what's being written, and the draft in progress.

    Every field is a primitive, because the state is a persisted wire format. A domain
    class here would tie old checkpoints to that class's import path, and LangGraph will
    refuse to deserialize unregistered types in a future version.
    """

    auth_user_id: int
    auth_user_identity: UUID
    text_type: str
    prompt_text: str
    draft_text: str = ""
    feedback_text: str | None = None
    rewrite_count: int = 0
    is_approved: bool = False

    def build_auth_user(self) -> AuthUser:
        """Groups the stored primitives back into the shape LlmService takes."""
        return AuthUser(id=self.auth_user_id, identity=self.auth_user_identity)
