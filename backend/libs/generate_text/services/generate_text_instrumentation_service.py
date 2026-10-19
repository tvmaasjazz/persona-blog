from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.errors import GraphBubbleUp

from libs.core.utils.date_time_utils import DateTimeUtils
from libs.generate_text.inputs import CreateGenerateTextStepInput
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType

GenerateTextNode = Callable[[GenerateTextState], Awaitable[dict[str, Any]]]


class GenerateTextInstrumentationService:
    """Wraps a node so every run of it is recorded as a step and timed."""

    def __init__(
        self,
        run_service: GenerateTextRunService,
        step_service: GenerateTextStepService,
    ) -> None:
        self._run_service = run_service
        self._step_service = step_service

    def instrument(
        self, node_type: GenerateTextNodeType, node: GenerateTextNode
    ) -> GenerateTextNode:
        """Fails the step and the run when the node raises, but lets a review pause through."""

        async def instrumented_node(state: GenerateTextState) -> dict[str, Any]:
            # Record the step as started
            step_name = node_type.value
            create_generate_text_step_input = CreateGenerateTextStepInput(
                run_id=state.generate_text_run_id, step_name=step_name, input=None
            )
            auth_user = state.build_auth_user()
            create_step_result = await self._step_service.create_step(
                create_generate_text_step_input, auth_user
            )
            step_id = create_step_result.id

            # Run the node, recording a pause or a failure
            node_state = state.model_copy(update={"current_step_id": step_id})

            start_time = DateTimeUtils.now_monotonic()
            try:
                node_result = await node(node_state)
            except GraphBubbleUp:
                # An interrupt is a review pause; the node reruns from the top on resume
                duration_ms = DateTimeUtils.elapsed_ms(start_time)
                await self._step_service.record_awaiting_review(step_id, duration_ms)
                raise
            except Exception as node_exception:
                duration_ms = DateTimeUtils.elapsed_ms(start_time)
                await self._step_service.fail_step(
                    step_id, type(node_exception).__name__, str(node_exception), duration_ms
                )
                await self._run_service.fail_run(state.generate_text_run_id)
                raise

            # Record the step as complete
            duration_ms = DateTimeUtils.elapsed_ms(start_time)
            step_output = self._resolve_step_output(node_result, step_name)
            await self._step_service.complete_step(step_id, step_output, duration_ms)

            return node_result

        return instrumented_node

    @staticmethod
    def _resolve_step_output(node_result: dict[str, Any], step_name: str) -> str:
        """Reads the output this node wrote under its own name."""
        step_outputs = node_result.get("step_outputs") or {}
        return step_outputs.get(step_name, "")
