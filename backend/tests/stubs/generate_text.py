from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import TextType


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

    async def ainvoke(
        self, graph_input: object, graph_run_config: dict[str, object]
    ) -> dict[str, object]:
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
