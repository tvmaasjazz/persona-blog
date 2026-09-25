from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.errors import GraphBubbleUp

from libs.core.utils.date_time_utils import DateTimeUtils
from libs.generate_text.inputs import CreateGenerateTextStepInput
from libs.generate_text.services.generate_text_rollup_service import GenerateTextRollupService
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType

GenerateTextNode = Callable[[GenerateTextState], Awaitable[dict[str, Any]]]


class GenerateTextInstrumentationService:
    """Wraps a node so every run of it is recorded as a step, timed, and rolled up. See
    plans/generate-text-engine.md, Instrumentation."""

    def __init__(
        self,
        run_service: GenerateTextRunService,
        step_service: GenerateTextStepService,
        rollup_service: GenerateTextRollupService,
    ) -> None:
        self._run_service = run_service
        self._step_service = step_service
        self._rollup_service = rollup_service

    def instrument(
        self, node_type: GenerateTextNodeType, node: GenerateTextNode
    ) -> GenerateTextNode:
        async def instrumented_node(state: GenerateTextState) -> dict[str, Any]:
            step_name = node_type.value
            create_generate_text_step_input = CreateGenerateTextStepInput(
                run_id=state.generate_text_run_id, step_name=step_name, input=None
            )
            auth_user = state.build_auth_user()
            create_step_result = await self._step_service.create_step(
                create_generate_text_step_input, auth_user
            )
            step_id = create_step_result.id

            await self._run_service.record_current_step(state.generate_text_run_id, step_name)

            node_state = state.model_copy(update={"current_step_id": step_id})

            start_time = DateTimeUtils.now_monotonic()
            try:
                node_result = await node(node_state)
            except GraphBubbleUp:
                # An interrupt is how a review node pauses, not a failure. LangGraph raises it
                # to suspend the run, and calls the node again from the top when it resumes.
                duration_ms = DateTimeUtils.elapsed_ms(start_time)
                await self._step_service.record_awaiting_review(step_id, duration_ms)
                raise
            except Exception as node_exception:
                duration_ms = DateTimeUtils.elapsed_ms(start_time)
                await self._step_service.fail_step(
                    step_id, type(node_exception).__name__, str(node_exception), duration_ms
                )
                await self._run_service.fail_run(
                    state.generate_text_run_id,
                    type(node_exception).__name__,
                    str(node_exception),
                    step_name,
                )
                raise

            duration_ms = DateTimeUtils.elapsed_ms(start_time)
            step_output = self._resolve_step_output(node_result, step_name)
            await self._step_service.complete_step(step_id, step_output, duration_ms)

            step_rollup_result = await self._rollup_service.build_step_rollup(step_id)
            await self._step_service.record_rollup(step_id, step_rollup_result)

            run_rollup_result = await self._rollup_service.build_run_rollup(
                state.generate_text_run_id
            )
            await self._run_service.record_rollup(state.generate_text_run_id, run_rollup_result)

            return node_result

        return instrumented_node

    @staticmethod
    def _resolve_step_output(node_result: dict[str, Any], step_name: str) -> str:
        """A node writes its output under its own name, so the step records what this
        node produced rather than whatever key happened to come last."""
        step_outputs = node_result.get("step_outputs") or {}
        return step_outputs.get(step_name, "")
