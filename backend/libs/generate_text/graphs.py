import functools

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.services import GenerateTextNodeService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType


def _route_after_review(
    state: GenerateTextState, generate_text_settings: GenerateTextSettings
) -> str:
    if state.is_approved or state.rewrite_count >= generate_text_settings.max_rewrite_passes:
        return END
    return GenerateTextNodeType.REWRITE_BLOG_POST


def build_generate_text_graph(
    generate_text_node_service: GenerateTextNodeService,
    generate_text_settings: GenerateTextSettings,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    route_after_review = functools.partial(
        _route_after_review, generate_text_settings=generate_text_settings
    )

    state_graph = StateGraph(GenerateTextState)
    # Every member is added, so a node type without a node fails here rather than at the
    # first run that reaches it.
    for node_type in GenerateTextNodeType:
        state_graph.add_node(node_type, generate_text_node_service.get_node(node_type))

    state_graph.add_edge(START, GenerateTextNodeType.WRITE_BLOG_POST)
    state_graph.add_edge(
        GenerateTextNodeType.WRITE_BLOG_POST, GenerateTextNodeType.REVIEW_BLOG_POST
    )
    state_graph.add_conditional_edges(
        GenerateTextNodeType.REVIEW_BLOG_POST,
        route_after_review,
        {
            END: END,
            GenerateTextNodeType.REWRITE_BLOG_POST: GenerateTextNodeType.REWRITE_BLOG_POST,
        },
    )
    state_graph.add_edge(
        GenerateTextNodeType.REWRITE_BLOG_POST, GenerateTextNodeType.REVIEW_BLOG_POST
    )

    return state_graph.compile(checkpointer=checkpointer)
