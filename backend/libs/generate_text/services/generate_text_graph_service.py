from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.graphs import GenerateTextGraphSpec
from libs.generate_text.types import TextType


class GenerateTextGraphService:
    """Maps a text type to the graph spec registered for it, the way LlmService maps a
    provider to its service. The specs arrive through __init__, so the engine never
    imports a text type and a new one is a new registration."""

    def __init__(self, generate_text_graph_specs: dict[TextType, GenerateTextGraphSpec]) -> None:
        self._generate_text_graph_specs = generate_text_graph_specs

    def current_graph_name(self, text_type: TextType) -> str:
        return self._resolve_spec(text_type).graph_name

    def current_graph_version(self, text_type: TextType) -> str:
        return self._resolve_spec(text_type).graph_version

    def build_graph(
        self,
        text_type: TextType,
        graph_version: str,
        options: dict[str, Any],
        checkpointer: BaseCheckpointSaver,
    ) -> CompiledStateGraph:
        generate_text_graph_spec = self._resolve_spec(text_type)
        if graph_version != generate_text_graph_spec.graph_version:
            # Running two versions side by side is what this parameter exists for; only the
            # current one resolves today.
            raise NotImplementedError(
                f"Graph version {graph_version} for {text_type} is not the current version"
            )
        return generate_text_graph_spec.build_graph(options, checkpointer)

    def _resolve_spec(self, text_type: TextType) -> GenerateTextGraphSpec:
        generate_text_graph_spec = self._generate_text_graph_specs.get(text_type)
        if generate_text_graph_spec is None:
            raise NotImplementedError(f"No graph registered for {text_type}")
        return generate_text_graph_spec
