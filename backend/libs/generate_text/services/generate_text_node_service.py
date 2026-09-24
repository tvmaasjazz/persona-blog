from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.types import interrupt

from libs.generate_text.constants import GENERATE_BLOG_POST_PURPOSE, REWRITE_BLOG_POST_PURPOSE
from libs.generate_text.prompts import GenerateTextPrompt
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType, TextType
from libs.llm.inputs import LlmCompletionInput
from libs.llm.services import LlmService
from libs.llm.types import LlmType

GenerateTextNode = Callable[[GenerateTextState], Awaitable[dict[str, Any]]]


class GenerateTextNodeService:
    """Holds the graph's nodes. The graph builder asks for each one by node type, so a
    node name is never a loose string and a member with no node fails at build time."""

    def __init__(self, llm_service: LlmService) -> None:
        self._llm_service = llm_service
        self._node_map: dict[GenerateTextNodeType, GenerateTextNode] = {
            GenerateTextNodeType.WRITE_BLOG_POST: self._write_blog_post,
            GenerateTextNodeType.REVIEW_BLOG_POST: self._review_blog_post,
            GenerateTextNodeType.REWRITE_BLOG_POST: self._rewrite_blog_post,
        }

    def get_node(self, node_type: GenerateTextNodeType) -> GenerateTextNode:
        generate_text_node = self._node_map.get(node_type)
        if generate_text_node is None:
            raise NotImplementedError(f"No node registered for {node_type}")
        return generate_text_node

    async def _write_blog_post(self, state: GenerateTextState) -> dict[str, Any]:
        text_type = TextType(state.text_type)
        llm_completion_input = LlmCompletionInput(
            llm_type=LlmType.STRONG,
            purpose=GENERATE_BLOG_POST_PURPOSE,
            system_prompt=GenerateTextPrompt.build_system_prompt(),
            user_prompt=GenerateTextPrompt.build_user_prompt(state.prompt_text, text_type),
        )
        auth_user = state.build_auth_user()
        completion_result = await self._llm_service.complete(llm_completion_input, auth_user)
        return {"draft_text": completion_result.content}

    async def _review_blog_post(self, state: GenerateTextState) -> dict[str, Any]:
        decision = interrupt({"draft_text": state.draft_text, "rewrite_count": state.rewrite_count})
        return {
            "is_approved": decision["is_approved"],
            "feedback_text": decision.get("feedback_text"),
        }

    async def _rewrite_blog_post(self, state: GenerateTextState) -> dict[str, Any]:
        rewrite_user_prompt = GenerateTextPrompt.build_rewrite_user_prompt(
            state.draft_text, state.feedback_text or ""
        )
        llm_completion_input = LlmCompletionInput(
            llm_type=LlmType.STRONG,
            purpose=REWRITE_BLOG_POST_PURPOSE,
            system_prompt=GenerateTextPrompt.build_system_prompt(),
            user_prompt=rewrite_user_prompt,
        )
        auth_user = state.build_auth_user()
        completion_result = await self._llm_service.complete(llm_completion_input, auth_user)
        return {
            "draft_text": completion_result.content,
            "rewrite_count": state.rewrite_count + 1,
        }
