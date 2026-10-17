import asyncio
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from libs.auth.results import AuthUser
from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
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
        self.ainvoke_error: Exception | None = None
        self.ainvoke_is_blocked = False
        self.ainvoke_started_event = asyncio.Event()

    async def ainvoke(
        self, graph_input: object, graph_run_config: dict[str, object]
    ) -> dict[str, object]:
        self.ainvoke_started_event.set()
        if self.ainvoke_is_blocked:
            await asyncio.Event().wait()
        if self.ainvoke_error is not None:
            raise self.ainvoke_error
        return {}


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
