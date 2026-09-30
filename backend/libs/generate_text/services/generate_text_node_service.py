from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.types import interrupt

from libs.generate_text.inputs import ResumeGenerateTextInput
from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType, HumanDecisionType
from libs.llm.inputs import LlmCompletionInput
from libs.llm.services import LlmService
from libs.llm.types import LlmType

GenerateTextNode = Callable[[GenerateTextState], Awaitable[dict[str, Any]]]


class GenerateTextNodeService:
    """Holds the nodes every text type's graph is built from. A node is generic: a
    text type supplies the node type it records under, the LLM tier, and its step's
    Prompt, through the three builders below, rather than this service knowing any
    text type's steps by name."""

    def __init__(self, llm_service: LlmService) -> None:
        self._llm_service = llm_service

    def build_generate_node(
        self,
        node_type: GenerateTextNodeType,
        llm_type: LlmType,
        prompt: BaseGenerateTextPrompt,
    ) -> GenerateTextNode:
        async def generate_node(state: GenerateTextState) -> dict[str, Any]:
            build_prompt_result = prompt.build_generate_prompt(state)
            llm_completion_input = LlmCompletionInput(
                llm_type=llm_type,
                purpose=node_type.value,
                system_prompt=build_prompt_result.system_prompt,
                user_prompt=build_prompt_result.user_prompt,
                run_id=state.generate_text_run_id,
                step_id=state.current_step_id,
            )
            auth_user = state.build_auth_user()
            completion_result = await self._llm_service.complete(llm_completion_input, auth_user)
            updated_step_outputs = {
                **state.step_outputs,
                node_type.value: completion_result.content,
            }
            return {"step_outputs": updated_step_outputs}

        return generate_node

    def build_rewrite_node(
        self,
        node_type: GenerateTextNodeType,
        llm_type: LlmType,
        reviewed_node_type: GenerateTextNodeType,
        prompt: BaseGenerateTextPrompt,
    ) -> GenerateTextNode:
        async def rewrite_node(state: GenerateTextState) -> dict[str, Any]:
            previous_output = state.latest_output()
            feedback_text = state.step_feedback.get(reviewed_node_type.value, "")
            build_prompt_result = prompt.build_rewrite_prompt(state, previous_output, feedback_text)
            llm_completion_input = LlmCompletionInput(
                llm_type=llm_type,
                purpose=node_type.value,
                system_prompt=build_prompt_result.system_prompt,
                user_prompt=build_prompt_result.user_prompt,
                run_id=state.generate_text_run_id,
                step_id=state.current_step_id,
            )
            auth_user = state.build_auth_user()
            completion_result = await self._llm_service.complete(llm_completion_input, auth_user)
            updated_step_outputs = {
                **state.step_outputs,
                node_type.value: completion_result.content,
            }
            previous_rewrite_count = state.rewrite_counts.get(reviewed_node_type.value, 0)
            updated_rewrite_counts = {
                **state.rewrite_counts,
                reviewed_node_type.value: previous_rewrite_count + 1,
            }
            return {"step_outputs": updated_step_outputs, "rewrite_counts": updated_rewrite_counts}

        return rewrite_node

    def build_review_node(self, node_type: GenerateTextNodeType) -> GenerateTextNode:
        async def review_node(state: GenerateTextState) -> dict[str, Any]:
            resume_payload = interrupt({"step_output": state.latest_output()})
            resume_generate_text_input = ResumeGenerateTextInput.model_validate(resume_payload)
            is_approved = resume_generate_text_input.is_approved
            feedback_text = resume_generate_text_input.feedback_text or ""
            human_decision = (
                HumanDecisionType.APPROVED if is_approved else HumanDecisionType.REJECTED
            )
            updated_step_decisions = {**state.step_decisions, node_type.value: human_decision.value}
            updated_step_feedback = {**state.step_feedback, node_type.value: feedback_text}
            return {
                "step_decisions": updated_step_decisions,
                "step_feedback": updated_step_feedback,
            }

        return review_node
