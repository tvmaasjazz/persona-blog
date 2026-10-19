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
    """Builds the compiled graph for one text type."""

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
