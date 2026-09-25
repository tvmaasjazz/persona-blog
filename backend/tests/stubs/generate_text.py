from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.types import TextType


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
