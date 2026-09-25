from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from libs.blog_post.constants import BLOG_POST_GRAPH_NAME, BLOG_POST_GRAPH_VERSION
from libs.blog_post.inputs import BlogPostOptionsInput
from libs.blog_post.prompts import BlogPostPrompt
from libs.generate_text.graphs import GenerateTextGraphSpec
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import (
    BuildGeneratePromptFn,
    BuildRewritePromptFn,
    GenerateTextNodeService,
)
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType, HumanDecisionType
from libs.llm.types import LlmType


@dataclass
class _StepSpec:
    """One blog post step: which nodes it wires, at what tier, from what prompts, and
    whether it needs a review node."""

    generate_node_type: GenerateTextNodeType
    rewrite_node_type: GenerateTextNodeType
    review_node_type: GenerateTextNodeType
    llm_type: LlmType
    build_generate_prompt: BuildGeneratePromptFn
    build_rewrite_prompt: BuildRewritePromptFn
    is_auto_approved: bool


def build_blog_post_graph(
    options: BlogPostOptionsInput,
    node_service: GenerateTextNodeService,
    instrumentation_service: GenerateTextInstrumentationService,
    generate_text_settings: GenerateTextSettings,
    checkpointer: BaseCheckpointSaver,
) -> CompiledStateGraph:
    step_specs = _build_step_specs(options)

    state_graph = StateGraph(GenerateTextState)
    for index, step_spec in enumerate(step_specs):
        next_entry = (
            step_specs[index + 1].generate_node_type if index + 1 < len(step_specs) else END
        )
        entry_edge_source = START if index == 0 else None
        _wire_step(
            state_graph,
            entry_edge_source,
            next_entry,
            step_spec,
            node_service,
            instrumentation_service,
            generate_text_settings,
        )

    return state_graph.compile(checkpointer=checkpointer)


def _build_step_specs(options: BlogPostOptionsInput) -> list[_StepSpec]:
    step_specs: list[_StepSpec] = []

    if options.outline is not None and options.outline.is_enabled:
        step_specs.append(
            _StepSpec(
                generate_node_type=GenerateTextNodeType.GENERATE_OUTLINE,
                rewrite_node_type=GenerateTextNodeType.REWRITE_OUTLINE,
                review_node_type=GenerateTextNodeType.REVIEW_OUTLINE,
                llm_type=LlmType.FAST,
                build_generate_prompt=_build_outline_user_prompt,
                build_rewrite_prompt=_build_rewrite_outline_user_prompt,
                is_auto_approved=options.outline.is_auto_approved,
            )
        )

    step_specs.append(
        _StepSpec(
            generate_node_type=GenerateTextNodeType.GENERATE_DRAFT,
            rewrite_node_type=GenerateTextNodeType.REWRITE_DRAFT,
            review_node_type=GenerateTextNodeType.REVIEW_DRAFT,
            llm_type=LlmType.STRONG,
            build_generate_prompt=_build_draft_user_prompt,
            build_rewrite_prompt=_build_rewrite_draft_user_prompt,
            is_auto_approved=options.draft.is_auto_approved,
        )
    )

    if options.humanize is not None and options.humanize.is_enabled:
        step_specs.append(
            _StepSpec(
                generate_node_type=GenerateTextNodeType.HUMANIZE,
                rewrite_node_type=GenerateTextNodeType.REWRITE_HUMANIZE,
                review_node_type=GenerateTextNodeType.REVIEW_HUMANIZE,
                llm_type=LlmType.STRONG,
                build_generate_prompt=_build_humanize_user_prompt,
                build_rewrite_prompt=_build_rewrite_humanize_user_prompt,
                is_auto_approved=options.humanize.is_auto_approved,
            )
        )

    return step_specs


def _wire_step(
    state_graph: StateGraph,
    entry_edge_source: str | None,
    next_entry: str,
    step_spec: _StepSpec,
    node_service: GenerateTextNodeService,
    instrumentation_service: GenerateTextInstrumentationService,
    generate_text_settings: GenerateTextSettings,
) -> None:
    generate_node = node_service.build_generate_node(
        step_spec.generate_node_type, step_spec.llm_type, step_spec.build_generate_prompt
    )
    state_graph.add_node(
        step_spec.generate_node_type,
        instrumentation_service.instrument(step_spec.generate_node_type, generate_node),
    )
    if entry_edge_source is not None:
        state_graph.add_edge(entry_edge_source, step_spec.generate_node_type)

    if step_spec.is_auto_approved:
        state_graph.add_edge(step_spec.generate_node_type, next_entry)
        return

    review_node = node_service.build_review_node(step_spec.review_node_type)
    state_graph.add_node(
        step_spec.review_node_type,
        instrumentation_service.instrument(step_spec.review_node_type, review_node),
    )
    state_graph.add_edge(step_spec.generate_node_type, step_spec.review_node_type)

    rewrite_node = node_service.build_rewrite_node(
        step_spec.rewrite_node_type,
        step_spec.llm_type,
        step_spec.review_node_type,
        step_spec.build_rewrite_prompt,
    )
    state_graph.add_node(
        step_spec.rewrite_node_type,
        instrumentation_service.instrument(step_spec.rewrite_node_type, rewrite_node),
    )
    state_graph.add_edge(step_spec.rewrite_node_type, step_spec.review_node_type)

    def route_after_review(state: GenerateTextState) -> str:
        return _route_after_review(
            state,
            step_spec.review_node_type,
            step_spec.rewrite_node_type,
            next_entry,
            generate_text_settings,
        )

    state_graph.add_conditional_edges(
        step_spec.review_node_type,
        route_after_review,
        {step_spec.rewrite_node_type: step_spec.rewrite_node_type, next_entry: next_entry},
    )


def _route_after_review(
    state: GenerateTextState,
    review_node_type: GenerateTextNodeType,
    rewrite_node_type: GenerateTextNodeType,
    next_entry: str,
    generate_text_settings: GenerateTextSettings,
) -> str:
    is_approved = (
        state.step_decisions.get(review_node_type.value) == HumanDecisionType.APPROVED.value
    )
    rewrite_count = state.rewrite_counts.get(review_node_type.value, 0)
    if is_approved or rewrite_count >= generate_text_settings.max_rewrite_passes:
        return next_entry
    return rewrite_node_type


def _build_outline_user_prompt(state: GenerateTextState) -> str:
    return BlogPostPrompt.build_outline_prompt(
        state.prompt_text, state.persona_info, state.additional_context
    )


def _build_draft_user_prompt(state: GenerateTextState) -> str:
    return BlogPostPrompt.build_draft_prompt(
        state.prompt_text, state.latest_output(), state.persona_info, state.additional_context
    )


def _build_humanize_user_prompt(state: GenerateTextState) -> str:
    return BlogPostPrompt.build_humanize_prompt(
        state.latest_output(), state.persona_info, state.additional_context
    )


def _build_rewrite_outline_user_prompt(
    state: GenerateTextState, previous_output: str, feedback_text: str
) -> str:
    return BlogPostPrompt.build_rewrite_outline_prompt(
        previous_output, feedback_text, state.persona_info, state.additional_context
    )


def _build_rewrite_draft_user_prompt(
    state: GenerateTextState, previous_output: str, feedback_text: str
) -> str:
    return BlogPostPrompt.build_rewrite_draft_prompt(
        previous_output, feedback_text, state.persona_info, state.additional_context
    )


def _build_rewrite_humanize_user_prompt(
    state: GenerateTextState, previous_output: str, feedback_text: str
) -> str:
    return BlogPostPrompt.build_rewrite_humanize_prompt(
        previous_output, feedback_text, state.persona_info, state.additional_context
    )


def build_blog_post_graph_spec(
    node_service: GenerateTextNodeService,
    instrumentation_service: GenerateTextInstrumentationService,
    generate_text_settings: GenerateTextSettings,
) -> GenerateTextGraphSpec:
    """Registers the blog post graph with the engine, binding the services its nodes need."""

    def build_graph(
        options: dict[str, Any], checkpointer: BaseCheckpointSaver
    ) -> CompiledStateGraph:
        blog_post_options_input = BlogPostOptionsInput.model_validate(options)
        return build_blog_post_graph(
            options=blog_post_options_input,
            node_service=node_service,
            instrumentation_service=instrumentation_service,
            generate_text_settings=generate_text_settings,
            checkpointer=checkpointer,
        )

    return GenerateTextGraphSpec(
        graph_name=BLOG_POST_GRAPH_NAME,
        graph_version=BLOG_POST_GRAPH_VERSION,
        build_graph=build_graph,
    )
