from uuid import UUID, uuid4

from libs.generate_text.inputs import GenerateTextInput, ResumeGenerateTextInput
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import TextType


def build_generate_text_input(
    *, text_type: TextType = TextType.BLOG_POST, prompt_text: str = "Write about coffee."
) -> GenerateTextInput:
    return GenerateTextInput(text_type=text_type, prompt_text=prompt_text)


def build_resume_generate_text_input(
    *, is_approved: bool = True, feedback_text: str | None = None
) -> ResumeGenerateTextInput:
    return ResumeGenerateTextInput(is_approved=is_approved, feedback_text=feedback_text)


def build_generate_text_state(
    *,
    auth_user_id: int = 1,
    auth_user_identity: UUID | None = None,
    text_type: TextType = TextType.BLOG_POST,
    prompt_text: str = "Write about coffee.",
    draft_text: str = "",
    feedback_text: str | None = None,
    rewrite_count: int = 0,
    is_approved: bool = False,
) -> GenerateTextState:
    return GenerateTextState(
        auth_user_id=auth_user_id,
        auth_user_identity=auth_user_identity or uuid4(),
        text_type=text_type,
        prompt_text=prompt_text,
        draft_text=draft_text,
        feedback_text=feedback_text,
        rewrite_count=rewrite_count,
        is_approved=is_approved,
    )
