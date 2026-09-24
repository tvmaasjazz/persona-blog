import functools

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.nodes import review_blog_post, rewrite_blog_post, write_blog_post
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.states import GenerateTextState
from libs.llm.services import LlmService


def _route_after_review(
    state: GenerateTextState, generate_text_settings: GenerateTextSettings
) -> str:
    if state.is_approved or state.rewrite_count >= generate_text_settings.max_rewrite_passes:
        return END
    return "rewrite_blog_post"


def build_generate_text_graph(
    llm_service: LlmService,
    generate_text_settings: GenerateTextSettings,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    write_blog_post_node = functools.partial(write_blog_post, llm_service=llm_service)
    rewrite_blog_post_node = functools.partial(rewrite_blog_post, llm_service=llm_service)
    route_after_review = functools.partial(
        _route_after_review, generate_text_settings=generate_text_settings
    )

    state_graph = StateGraph(GenerateTextState)
    state_graph.add_node("write_blog_post", write_blog_post_node)
    state_graph.add_node("review_blog_post", review_blog_post)
    state_graph.add_node("rewrite_blog_post", rewrite_blog_post_node)

    state_graph.add_edge(START, "write_blog_post")
    state_graph.add_edge("write_blog_post", "review_blog_post")
    state_graph.add_conditional_edges(
        "review_blog_post",
        route_after_review,
        {END: END, "rewrite_blog_post": "rewrite_blog_post"},
    )
    state_graph.add_edge("rewrite_blog_post", "review_blog_post")

    return state_graph.compile(checkpointer=checkpointer)
