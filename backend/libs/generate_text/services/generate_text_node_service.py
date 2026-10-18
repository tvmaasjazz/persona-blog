from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.types import interrupt

from libs.generate_text.exceptions import GenerateTextOutputInvalidException
from libs.generate_text.inputs import ResumeGenerateTextInput
from libs.generate_text.output_formats import BaseGenerateTextOutputFormat
from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType, HumanDecisionType
from libs.llm.inputs import LlmCompletionInput
from libs.llm.services import LlmService
from libs.llm.types import LlmType

GenerateTextNode = Callable[[GenerateTextState], Awaitable[dict[str, Any]]]

OUTPUT_FORMAT_PROBLEMS_USER_PROMPT_TEMPLATE = (
    "{user_prompt}\n\n"
    "Your previous response had these problems. Fix them and return the whole post "
    "again:\n{problems_text}"
)


class GenerateTextNodeService:
    """Builds the generate, rewrite and review nodes every text type's graph uses."""

    def __init__(
        self, llm_service: LlmService, generate_text_settings: GenerateTextSettings
    ) -> None:
        self._llm_service = llm_service
        self._generate_text_settings = generate_text_settings

    def build_generate_node(
        self,
        node_type: GenerateTextNodeType,
        llm_type: LlmType,
        prompt: BaseGenerateTextPrompt,
        output_format: BaseGenerateTextOutputFormat | None = None,
    ) -> GenerateTextNode:
        async def generate_node(state: GenerateTextState) -> dict[str, Any]:
            build_prompt_result = prompt.build_generate_prompt(state)
            output_text = await self._complete_with_output_format(
                state, node_type, llm_type, build_prompt_result, output_format
            )
            updated_step_outputs = {**state.step_outputs, node_type.value: output_text}
            return {"step_outputs": updated_step_outputs}

        return generate_node

    def build_rewrite_node(
        self,
        node_type: GenerateTextNodeType,
        llm_type: LlmType,
        reviewed_node_type: GenerateTextNodeType,
        prompt: BaseGenerateTextPrompt,
        output_format: BaseGenerateTextOutputFormat | None = None,
    ) -> GenerateTextNode:
        async def rewrite_node(state: GenerateTextState) -> dict[str, Any]:
            previous_output = state.latest_output()
            feedback_text = state.step_feedback.get(reviewed_node_type.value, "")
            build_prompt_result = prompt.build_rewrite_prompt(state, previous_output, feedback_text)
            output_text = await self._complete_with_output_format(
                state, node_type, llm_type, build_prompt_result, output_format
            )
            updated_step_outputs = {**state.step_outputs, node_type.value: output_text}
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

    async def _complete_with_output_format(
        self,
        state: GenerateTextState,
        node_type: GenerateTextNodeType,
        llm_type: LlmType,
        build_prompt_result: BuildPromptResult,
        output_format: BaseGenerateTextOutputFormat | None,
    ) -> str:
        auth_user = state.build_auth_user()
        system_prompt = build_prompt_result.system_prompt
        user_prompt = build_prompt_result.user_prompt
        max_attempts = self._generate_text_settings.max_output_format_retries + 1

        error_messages: list[str] = []
        for attempt_number in range(1, max_attempts + 1):
            # Call the LLM
            llm_completion_input = LlmCompletionInput(
                llm_type=llm_type,
                purpose=node_type.value,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                run_id=state.generate_text_run_id,
                step_id=state.current_step_id,
            )
            completion_result = await self._llm_service.complete(llm_completion_input, auth_user)

            if output_format is None:
                return completion_result.content

            # Accept output that follows the format
            normalized_text = output_format.normalize_output(completion_result.content)
            validate_output_result = output_format.validate_output(normalized_text)
            error_messages = validate_output_result.error_messages
            if not error_messages:
                return normalized_text

            # Retry with the problems added to the user prompt
            if attempt_number < max_attempts:
                problems_text = "\n".join(f"- {error_message}" for error_message in error_messages)
                user_prompt = OUTPUT_FORMAT_PROBLEMS_USER_PROMPT_TEMPLATE.format(
                    user_prompt=build_prompt_result.user_prompt, problems_text=problems_text
                )

        # Out of retries
        problems_text = "\n".join(error_messages)
        raise GenerateTextOutputInvalidException(
            f"{node_type.value} produced output that does not follow the required "
            f"format:\n{problems_text}"
        )
