from langgraph.types import interrupt

from libs.auth.results import AuthUser
from libs.generate_text.constants import GENERATE_BLOG_POST_PURPOSE, REWRITE_BLOG_POST_PURPOSE
from libs.generate_text.prompts import GenerateTextPrompt
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import TextType
from libs.llm.inputs import LlmCompletionInput
from libs.llm.services import LlmService
from libs.llm.types import LlmType


async def write_blog_post(state: GenerateTextState, llm_service: LlmService) -> dict:
    system_prompt = GenerateTextPrompt.build_system_prompt()
    text_type = TextType(state.text_type)
    user_prompt = GenerateTextPrompt.build_user_prompt(state.prompt_text, text_type)
    llm_completion_input = LlmCompletionInput(
        llm_type=LlmType.STRONG,
        purpose=GENERATE_BLOG_POST_PURPOSE,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    auth_user = _build_auth_user(state)
    completion_result = await llm_service.complete(llm_completion_input, auth_user)
    return {"draft_text": completion_result.content}


async def review_blog_post(state: GenerateTextState) -> dict:
    decision = interrupt({"draft_text": state.draft_text, "rewrite_count": state.rewrite_count})
    return {"is_approved": decision["is_approved"], "feedback_text": decision.get("feedback_text")}


async def rewrite_blog_post(state: GenerateTextState, llm_service: LlmService) -> dict:
    system_prompt = GenerateTextPrompt.build_system_prompt()
    user_prompt = GenerateTextPrompt.build_rewrite_user_prompt(
        state.draft_text, state.feedback_text or ""
    )
    llm_completion_input = LlmCompletionInput(
        llm_type=LlmType.STRONG,
        purpose=REWRITE_BLOG_POST_PURPOSE,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    auth_user = _build_auth_user(state)
    completion_result = await llm_service.complete(llm_completion_input, auth_user)
    return {"draft_text": completion_result.content, "rewrite_count": state.rewrite_count + 1}


def _build_auth_user(state: GenerateTextState) -> AuthUser:
    """The state stores the acting user as primitives; LlmService takes the AuthUser."""
    return AuthUser(id=state.auth_user_id, identity=state.auth_user_identity)
