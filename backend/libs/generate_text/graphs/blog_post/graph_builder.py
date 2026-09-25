from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.graphs.blog_post.prompts import BlogPostPrompt
from libs.generate_text.services.generate_text_node_service import (
    BuildGeneratePromptFn,
    BuildRewritePromptFn,
)
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


class BlogPostGraphBuilder(BaseGenerateTextGraphBuilder):
    """Builds the blog post graph: outline (optional) → draft → humanize (optional),
    each reviewable step followed by its own review/rewrite loop. See
    plans/generate-text-engine.md, "The graph a builder produces"."""

    graph_name = "blog_post"
    graph_version = "2026-09-24.1"

    def build_graph(
        self, options: dict[str, Any], checkpointer: BaseCheckpointSaver
    ) -> CompiledStateGraph:
        blog_post_options_input = BlogPostOptionsInput.model_validate(options)
        step_specs = self._build_step_specs(blog_post_options_input)

        state_graph = StateGraph(GenerateTextState)
        for index, step_spec in enumerate(step_specs):
            # The node this step hands off to once it's done: the next enabled step's
            # generate node, or END if this is the last one.
            next_entry = (
                step_specs[index + 1].generate_node_type if index + 1 < len(step_specs) else END
            )
            # Only the very first step wires an edge in from START; later steps are
            # entered from the step before them.
            entry_edge_source = START if index == 0 else None
            self._wire_step(state_graph, entry_edge_source, next_entry, step_spec)

        return state_graph.compile(checkpointer=checkpointer)

    def _build_step_specs(self, options: BlogPostOptionsInput) -> list[_StepSpec]:
        """The ordered list of steps this run's topology is built from. A step is
        included only when the caller enabled it; draft always runs, since a blog post
        without a draft isn't one."""
        step_specs: list[_StepSpec] = []

        if options.outline is not None and options.outline.is_enabled:
            step_specs.append(
                _StepSpec(
                    generate_node_type=GenerateTextNodeType.GENERATE_OUTLINE,
                    rewrite_node_type=GenerateTextNodeType.REWRITE_OUTLINE,
                    review_node_type=GenerateTextNodeType.REVIEW_OUTLINE,
                    llm_type=LlmType.FAST,
                    build_generate_prompt=self._build_outline_user_prompt,
                    build_rewrite_prompt=self._build_rewrite_outline_user_prompt,
                    is_auto_approved=options.outline.is_auto_approved,
                )
            )

        step_specs.append(
            _StepSpec(
                generate_node_type=GenerateTextNodeType.GENERATE_DRAFT,
                rewrite_node_type=GenerateTextNodeType.REWRITE_DRAFT,
                review_node_type=GenerateTextNodeType.REVIEW_DRAFT,
                llm_type=LlmType.STRONG,
                build_generate_prompt=self._build_draft_user_prompt,
                build_rewrite_prompt=self._build_rewrite_draft_user_prompt,
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
                    build_generate_prompt=self._build_humanize_user_prompt,
                    build_rewrite_prompt=self._build_rewrite_humanize_user_prompt,
                    is_auto_approved=options.humanize.is_auto_approved,
                )
            )

        return step_specs

    def _wire_step(
        self,
        state_graph: StateGraph,
        entry_edge_source: str | None,
        next_entry: str,
        step_spec: _StepSpec,
    ) -> None:
        # Every step gets a generate node: the first pass at this step's output.
        generate_node = self._node_service.build_generate_node(
            step_spec.generate_node_type, step_spec.llm_type, step_spec.build_generate_prompt
        )
        state_graph.add_node(
            step_spec.generate_node_type,
            self._instrumentation_service.instrument(step_spec.generate_node_type, generate_node),
        )
        if entry_edge_source is not None:
            state_graph.add_edge(entry_edge_source, step_spec.generate_node_type)

        if step_spec.is_auto_approved:
            # No review node: the generate node's output goes straight on to whatever
            # follows this step.
            state_graph.add_edge(step_spec.generate_node_type, next_entry)
            return

        # Review node: calls interrupt() to pause the graph until a human approves or
        # rejects this step's output.
        review_node = self._node_service.build_review_node(step_spec.review_node_type)
        state_graph.add_node(
            step_spec.review_node_type,
            self._instrumentation_service.instrument(step_spec.review_node_type, review_node),
        )
        state_graph.add_edge(step_spec.generate_node_type, step_spec.review_node_type)

        # Rewrite node: its own node, not a rerun of generate, because it's its own
        # prompt — the previous output plus the reviewer's feedback — and can run on a
        # different tier. It feeds back into the same review node, so a reviewer can
        # reject more than once, bounded by max_rewrite_passes.
        rewrite_node = self._node_service.build_rewrite_node(
            step_spec.rewrite_node_type,
            step_spec.llm_type,
            step_spec.review_node_type,
            step_spec.build_rewrite_prompt,
        )
        state_graph.add_node(
            step_spec.rewrite_node_type,
            self._instrumentation_service.instrument(step_spec.rewrite_node_type, rewrite_node),
        )
        state_graph.add_edge(step_spec.rewrite_node_type, step_spec.review_node_type)

        def route_after_review(state: GenerateTextState) -> str:
            return self._route_after_review(
                state, step_spec.review_node_type, step_spec.rewrite_node_type, next_entry
            )

        # After a review, either the decision was approved (or the rewrite budget ran
        # out), and the graph moves on, or it was rejected and loops back through rewrite.
        state_graph.add_conditional_edges(
            step_spec.review_node_type,
            route_after_review,
            {step_spec.rewrite_node_type: step_spec.rewrite_node_type, next_entry: next_entry},
        )

    def _route_after_review(
        self,
        state: GenerateTextState,
        review_node_type: GenerateTextNodeType,
        rewrite_node_type: GenerateTextNodeType,
        next_entry: str,
    ) -> str:
        is_approved = (
            state.step_decisions.get(review_node_type.value) == HumanDecisionType.APPROVED.value
        )
        rewrite_count = state.rewrite_counts.get(review_node_type.value, 0)
        if is_approved or rewrite_count >= self._generate_text_settings.max_rewrite_passes:
            return next_entry
        return rewrite_node_type

    @staticmethod
    def _build_outline_user_prompt(state: GenerateTextState) -> str:
        return BlogPostPrompt.build_outline_prompt(
            state.prompt_text, state.persona_info, state.additional_context
        )

    @staticmethod
    def _build_draft_user_prompt(state: GenerateTextState) -> str:
        return BlogPostPrompt.build_draft_prompt(
            state.prompt_text, state.latest_output(), state.persona_info, state.additional_context
        )

    @staticmethod
    def _build_humanize_user_prompt(state: GenerateTextState) -> str:
        return BlogPostPrompt.build_humanize_prompt(
            state.latest_output(), state.persona_info, state.additional_context
        )

    @staticmethod
    def _build_rewrite_outline_user_prompt(
        state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> str:
        return BlogPostPrompt.build_rewrite_outline_prompt(
            previous_output, feedback_text, state.persona_info, state.additional_context
        )

    @staticmethod
    def _build_rewrite_draft_user_prompt(
        state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> str:
        return BlogPostPrompt.build_rewrite_draft_prompt(
            previous_output, feedback_text, state.persona_info, state.additional_context
        )

    @staticmethod
    def _build_rewrite_humanize_user_prompt(
        state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> str:
        return BlogPostPrompt.build_rewrite_humanize_prompt(
            previous_output, feedback_text, state.persona_info, state.additional_context
        )
