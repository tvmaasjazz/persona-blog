import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from libs.auth.results import AuthUser
from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.services.generate_text_run_pickup_service import (
    GenerateTextRunPickupService,
)
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import HumanDecisionType, TextType


class GenerateTextPromptStub(BaseGenerateTextPrompt):
    """A Prompt double that returns fixed BuildPromptResults, so a test can assert a
    node service passes them through to the llm without depending on any real step's
    template text."""

    def __init__(self) -> None:
        self.build_generate_prompt_result = BuildPromptResult(
            system_prompt="Stub generate system prompt.",
            user_prompt="Stub generate user prompt.",
        )
        self.build_rewrite_prompt_result = BuildPromptResult(
            system_prompt="Stub rewrite system prompt.",
            user_prompt="Stub rewrite user prompt.",
        )

    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult:
        return self.build_generate_prompt_result

    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult:
        return self.build_rewrite_prompt_result


class GenerateTextGraphStub(CompiledStateGraph):
    def __init__(self) -> None:
        self.astream_inputs: list[object] = []
        self.astream_chunks: list[dict[str, object]] = []
        self.astream_error: Exception | None = None
        self.astream_is_blocked = False
        self.astream_is_cancelled = False
        self.astream_started_event = asyncio.Event()
        self.aget_state_result = StateSnapshot(
            values={},
            next=(),
            config={},
            metadata=None,
            created_at=None,
            parent_config=None,
            tasks=(),
            interrupts=(),
        )

    async def astream(
        self,
        graph_input: object,
        graph_run_config: dict[str, object],
        *,
        stream_mode: str,
        durability: str,
    ) -> AsyncIterator[dict[str, object]]:
        self.astream_inputs.append(graph_input)
        self.astream_started_event.set()
        if self.astream_is_blocked:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.astream_is_cancelled = True
                raise
        if self.astream_error is not None:
            raise self.astream_error
        for astream_chunk in self.astream_chunks:
            yield astream_chunk

    async def aget_state(self, graph_run_config: dict[str, object]) -> StateSnapshot:
        return self.aget_state_result


class GenerateTextGraphBuilderStub(BaseGenerateTextGraphBuilder):
    graph_name = "stub"
    graph_version = "stub-version"

    def __init__(self) -> None:
        self.build_graph_result = GenerateTextGraphStub()

    def build_graph(
        self, options: dict[str, Any], checkpointer: BaseCheckpointSaver
    ) -> CompiledStateGraph:
        return self.build_graph_result


class GenerateTextGraphBuilderRegistryStub(GenerateTextGraphBuilderRegistry):
    def __init__(self) -> None:
        self.get_by_text_type_result: BaseGenerateTextGraphBuilder = GenerateTextGraphBuilderStub()

    def get_by_text_type(self, text_type: TextType) -> BaseGenerateTextGraphBuilder:
        return self.get_by_text_type_result


class GenerateTextStepServiceStub(GenerateTextStepService):
    def __init__(self) -> None:
        self.find_awaiting_review_step_id_inputs: list[int] = []
        self.find_awaiting_review_step_id_result: int | None = 1
        self.record_decision_error: Exception | None = None

    async def find_awaiting_review_step_id(self, run_id: int) -> int | None:
        self.find_awaiting_review_step_id_inputs.append(run_id)
        return self.find_awaiting_review_step_id_result

    async def record_decision(
        self,
        step_id: int,
        human_decision: HumanDecisionType,
        human_feedback: str | None,
        auth_user: AuthUser,
        decided_at: datetime,
    ) -> None:
        if self.record_decision_error is not None:
            raise self.record_decision_error


class GenerateTextRunServiceStub(GenerateTextRunService):
    """Wraps a real run service so a test can wait for a lease renewal, make one fail,
    or read the renewals it saw, while the renewals that succeed still write the row."""

    def __init__(self, run_service: GenerateTextRunService) -> None:
        self._run_service = run_service
        self.renew_lease_inputs: list[tuple[int, str, datetime]] = []
        self.renew_lease_error: Exception | None = None
        self.renew_lease_event = asyncio.Event()

    async def renew_lease(self, run_id: int, lease_owner: str, lease_expires_at: datetime) -> bool:
        self.renew_lease_inputs.append((run_id, lease_owner, lease_expires_at))
        try:
            if self.renew_lease_error is not None:
                raise self.renew_lease_error
            return await self._run_service.renew_lease(run_id, lease_owner, lease_expires_at)
        finally:
            self.renew_lease_event.set()


class GenerateTextRunPickupServiceStub(GenerateTextRunPickupService):
    """Overrides pick_up_expired_run only, so a test drives the real sweep loop. The loop
    reads the sweep interval from the settings the real __init__ would have stored."""

    def __init__(self, *, run_sweep_interval_seconds: int) -> None:
        self._generate_text_settings = GenerateTextSettings(
            run_sweep_interval_seconds=run_sweep_interval_seconds
        )
        self.pick_up_expired_run_call_count = 0
        self.pick_up_expired_run_results: list[bool | Exception] = []
        self.pick_up_expired_run_exhausted_event = asyncio.Event()

    async def pick_up_expired_run(self) -> bool:
        self.pick_up_expired_run_call_count += 1
        pick_up_expired_run_result = self.pick_up_expired_run_results.pop(0)
        if not self.pick_up_expired_run_results:
            self.pick_up_expired_run_exhausted_event.set()
        if isinstance(pick_up_expired_run_result, Exception):
            raise pick_up_expired_run_result
        return pick_up_expired_run_result
