from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

from libs.generate_text.exceptions import GenerateTextOptionsInvalidException
from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.graphs.blog_post.prompts import (
    BlogPostDraftPrompt,
    BlogPostHumanizePrompt,
    BlogPostOutlinePrompt,
)
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType, HumanDecisionType
from libs.llm.types import LlmType


class BlogPostGraphBuilder(BaseGenerateTextGraphBuilder):
    """Builds the blog post graph: outline (optional) → draft → humanize (optional),
    with a review and rewrite loop around any step the caller didn't auto-approve.

    Every node and edge is written out here rather than generated from a table, so the
    whole topology reads top to bottom. That repeats the review-and-rewrite block once
    per reviewable step; worth revisiting if this ever grows past a handful of steps.
    """

    graph_name = "blog_post"
    graph_version = "2026-09-30.1"

    def build_graph(
        self, options: dict[str, Any], checkpointer: BaseCheckpointSaver
    ) -> CompiledStateGraph:
        try:
            blog_post_options = BlogPostOptionsInput.model_validate(options)
        except ValidationError as validation_error:
            # Options a text type can't read are the caller's mistake, not a 500. A
            # pydantic error must not reach apps/ (fastapi-structure.md > Errors).
            raise GenerateTextOptionsInvalidException(
                "These options are not valid for a blog post"
            ) from validation_error

        outline_prompt = BlogPostOutlinePrompt()
        draft_prompt = BlogPostDraftPrompt()
        humanize_prompt = BlogPostHumanizePrompt()

        outline_options = blog_post_options.outline
        humanize_options = blog_post_options.humanize
        is_outline_enabled = outline_options is not None and outline_options.is_enabled
        is_humanize_enabled = humanize_options is not None and humanize_options.is_enabled

        # Where each step hands off, decided by which later steps the caller enabled.
        after_draft = GenerateTextNodeType.HUMANIZE if is_humanize_enabled else END
        after_outline = GenerateTextNodeType.GENERATE_DRAFT
        first_node = (
            GenerateTextNodeType.GENERATE_OUTLINE
            if is_outline_enabled
            else GenerateTextNodeType.GENERATE_DRAFT
        )

        state_graph = StateGraph(GenerateTextState)
        state_graph.add_edge(START, first_node)

        # Outline: a cheap pass at the shape of the post, before anything writes prose.
        if outline_options is not None and outline_options.is_enabled:
            outline_node = self._node_service.build_generate_node(
                GenerateTextNodeType.GENERATE_OUTLINE, LlmType.FAST, outline_prompt
            )
            state_graph.add_node(
                GenerateTextNodeType.GENERATE_OUTLINE,
                self._instrumentation_service.instrument(
                    GenerateTextNodeType.GENERATE_OUTLINE, outline_node
                ),
            )

            if outline_options.is_auto_approved:
                state_graph.add_edge(GenerateTextNodeType.GENERATE_OUTLINE, after_outline)
            else:
                review_outline_node = self._node_service.build_review_node(
                    GenerateTextNodeType.REVIEW_OUTLINE
                )
                state_graph.add_node(
                    GenerateTextNodeType.REVIEW_OUTLINE,
                    self._instrumentation_service.instrument(
                        GenerateTextNodeType.REVIEW_OUTLINE, review_outline_node
                    ),
                )
                # A rewrite is its own node, not a rerun: its own prompt, and its own
                # tier, which is why an outline rewrite can stay cheap.
                rewrite_outline_node = self._node_service.build_rewrite_node(
                    GenerateTextNodeType.REWRITE_OUTLINE,
                    LlmType.FAST,
                    GenerateTextNodeType.REVIEW_OUTLINE,
                    outline_prompt,
                )
                state_graph.add_node(
                    GenerateTextNodeType.REWRITE_OUTLINE,
                    self._instrumentation_service.instrument(
                        GenerateTextNodeType.REWRITE_OUTLINE, rewrite_outline_node
                    ),
                )
                state_graph.add_edge(
                    GenerateTextNodeType.GENERATE_OUTLINE, GenerateTextNodeType.REVIEW_OUTLINE
                )
                state_graph.add_edge(
                    GenerateTextNodeType.REWRITE_OUTLINE, GenerateTextNodeType.REVIEW_OUTLINE
                )
                state_graph.add_conditional_edges(
                    GenerateTextNodeType.REVIEW_OUTLINE,
                    lambda state: self._route_after_review(
                        state,
                        GenerateTextNodeType.REVIEW_OUTLINE,
                        GenerateTextNodeType.REWRITE_OUTLINE,
                        after_outline,
                    ),
                    {
                        GenerateTextNodeType.REWRITE_OUTLINE: GenerateTextNodeType.REWRITE_OUTLINE,
                        after_outline: after_outline,
                    },
                )

        # Draft: always runs. A blog post without a draft isn't one.
        draft_node = self._node_service.build_generate_node(
            GenerateTextNodeType.GENERATE_DRAFT, LlmType.STRONG, draft_prompt
        )
        state_graph.add_node(
            GenerateTextNodeType.GENERATE_DRAFT,
            self._instrumentation_service.instrument(
                GenerateTextNodeType.GENERATE_DRAFT, draft_node
            ),
        )

        if blog_post_options.draft.is_auto_approved:
            state_graph.add_edge(GenerateTextNodeType.GENERATE_DRAFT, after_draft)
        else:
            review_draft_node = self._node_service.build_review_node(
                GenerateTextNodeType.REVIEW_DRAFT
            )
            state_graph.add_node(
                GenerateTextNodeType.REVIEW_DRAFT,
                self._instrumentation_service.instrument(
                    GenerateTextNodeType.REVIEW_DRAFT, review_draft_node
                ),
            )
            rewrite_draft_node = self._node_service.build_rewrite_node(
                GenerateTextNodeType.REWRITE_DRAFT,
                LlmType.STRONG,
                GenerateTextNodeType.REVIEW_DRAFT,
                draft_prompt,
            )
            state_graph.add_node(
                GenerateTextNodeType.REWRITE_DRAFT,
                self._instrumentation_service.instrument(
                    GenerateTextNodeType.REWRITE_DRAFT, rewrite_draft_node
                ),
            )
            state_graph.add_edge(
                GenerateTextNodeType.GENERATE_DRAFT, GenerateTextNodeType.REVIEW_DRAFT
            )
            state_graph.add_edge(
                GenerateTextNodeType.REWRITE_DRAFT, GenerateTextNodeType.REVIEW_DRAFT
            )
            state_graph.add_conditional_edges(
                GenerateTextNodeType.REVIEW_DRAFT,
                lambda state: self._route_after_review(
                    state,
                    GenerateTextNodeType.REVIEW_DRAFT,
                    GenerateTextNodeType.REWRITE_DRAFT,
                    after_draft,
                ),
                {
                    GenerateTextNodeType.REWRITE_DRAFT: GenerateTextNodeType.REWRITE_DRAFT,
                    after_draft: after_draft,
                },
            )

        # Humanize: a last pass over the draft, when the caller asked for one.
        if humanize_options is not None and humanize_options.is_enabled:
            humanize_node = self._node_service.build_generate_node(
                GenerateTextNodeType.HUMANIZE, LlmType.STRONG, humanize_prompt
            )
            state_graph.add_node(
                GenerateTextNodeType.HUMANIZE,
                self._instrumentation_service.instrument(
                    GenerateTextNodeType.HUMANIZE, humanize_node
                ),
            )

            if humanize_options.is_auto_approved:
                state_graph.add_edge(GenerateTextNodeType.HUMANIZE, END)
            else:
                review_humanize_node = self._node_service.build_review_node(
                    GenerateTextNodeType.REVIEW_HUMANIZE
                )
                state_graph.add_node(
                    GenerateTextNodeType.REVIEW_HUMANIZE,
                    self._instrumentation_service.instrument(
                        GenerateTextNodeType.REVIEW_HUMANIZE, review_humanize_node
                    ),
                )
                rewrite_humanize_node = self._node_service.build_rewrite_node(
                    GenerateTextNodeType.REWRITE_HUMANIZE,
                    LlmType.STRONG,
                    GenerateTextNodeType.REVIEW_HUMANIZE,
                    humanize_prompt,
                )
                state_graph.add_node(
                    GenerateTextNodeType.REWRITE_HUMANIZE,
                    self._instrumentation_service.instrument(
                        GenerateTextNodeType.REWRITE_HUMANIZE, rewrite_humanize_node
                    ),
                )
                state_graph.add_edge(
                    GenerateTextNodeType.HUMANIZE, GenerateTextNodeType.REVIEW_HUMANIZE
                )
                state_graph.add_edge(
                    GenerateTextNodeType.REWRITE_HUMANIZE, GenerateTextNodeType.REVIEW_HUMANIZE
                )
                state_graph.add_conditional_edges(
                    GenerateTextNodeType.REVIEW_HUMANIZE,
                    lambda state: self._route_after_review(
                        state,
                        GenerateTextNodeType.REVIEW_HUMANIZE,
                        GenerateTextNodeType.REWRITE_HUMANIZE,
                        END,
                    ),
                    {
                        GenerateTextNodeType.REWRITE_HUMANIZE: (
                            GenerateTextNodeType.REWRITE_HUMANIZE
                        ),
                        END: END,
                    },
                )

        return state_graph.compile(checkpointer=checkpointer)

    def _route_after_review(
        self,
        state: GenerateTextState,
        review_node_type: GenerateTextNodeType,
        rewrite_node_type: GenerateTextNodeType,
        next_entry: str,
    ) -> str:
        """Approved, or out of rewrite passes, and the run moves on; rejected, and it
        loops back through the rewrite node into the same review."""
        is_approved = (
            state.step_decisions.get(review_node_type.value) == HumanDecisionType.APPROVED.value
        )
        rewrite_count = state.rewrite_counts.get(review_node_type.value, 0)
        if is_approved or rewrite_count >= self._generate_text_settings.max_rewrite_passes:
            return next_entry
        return rewrite_node_type
