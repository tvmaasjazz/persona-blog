from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

GraphBuilderFn = Callable[[dict[str, Any], BaseCheckpointSaver], CompiledStateGraph]


@dataclass(frozen=True)
class GenerateTextGraphSpec:
    """What a text type registers with the engine: how its graph is named, which version
    is current, and how to build it. The engine holds no import of any text type — the
    dependency factory passes the specs in, the way the LLM provider map is passed in."""

    graph_name: str
    graph_version: str
    build_graph: GraphBuilderFn
