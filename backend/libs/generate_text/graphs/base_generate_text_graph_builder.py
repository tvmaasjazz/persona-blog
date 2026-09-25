from abc import ABC, abstractmethod
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.settings import GenerateTextSettings


class BaseGenerateTextGraphBuilder(ABC):
    """A text type's graph builder: names its graph, knows its current version, and
    builds the compiled graph a run needs. graph_name and graph_version are plain class
    attributes, not properties, because they are fixed per builder and read with no
    computation — a property would only add indirection.

    Every builder takes the shared node and instrumentation services and the engine's
    settings through __init__, since every text type's graph is wired from the same
    nodes and rewrite budget."""

    graph_name: str
    graph_version: str

    def __init__(
        self,
        node_service: GenerateTextNodeService,
        instrumentation_service: GenerateTextInstrumentationService,
        generate_text_settings: GenerateTextSettings,
    ) -> None:
        self._node_service = node_service
        self._instrumentation_service = instrumentation_service
        self._generate_text_settings = generate_text_settings

    @abstractmethod
    def build_graph(
        self, options: dict[str, Any], checkpointer: BaseCheckpointSaver
    ) -> CompiledStateGraph: ...
