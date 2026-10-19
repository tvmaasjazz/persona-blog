from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError

from libs.generate_text.exceptions import GenerateTextOptionsInvalidException
from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.blog_post.blog_post_body_output_format import (
    BlogPostBodyOutputFormat,
)
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
    """Builds the blog post graph, with a review loop around each step not auto-approved."""

    graph_name = "blog_post"
    graph_version = "2026-10-07.2"

    def build_graph(
        self, options: dict[str, Any], checkpointer: BaseCheckpointSaver
    ) -> CompiledStateGraph:
        # Validate the caller's options
        try:
            blog_post_options = BlogPostOptionsInput.model_validate(options)
        except ValidationError as validation_error:
            # Invalid options are the caller's mistake; don't leak the pydantic error
            raise GenerateTextOptionsInvalidException(
                "These options are not valid for a blog post"
            ) from validation_error

        # Prompts, output format and enabled steps
        outline_prompt = BlogPostOutlinePrompt()
        draft_prompt = BlogPostDraftPrompt()
        humanize_prompt = BlogPostHumanizePrompt()
        blog_post_body_output_format = BlogPostBodyOutputFormat()

        outline_options = blog_post_options.outline
        humanize_options = blog_post_options.humanize
        is_outline_enabled = outline_options is not None and outline_options.is_enabled
        is_humanize_enabled = humanize_options is not None and humanize_options.is_enabled

        # Where each step hands off, by which later steps are enabled
        after_draft = GenerateTextNodeType.HUMANIZE if is_humanize_enabled else END
        after_outline = GenerateTextNodeType.GENERATE_DRAFT
        first_node = (
            GenerateTextNodeType.GENERATE_OUTLINE
            if is_outline_enabled
            else GenerateTextNodeType.GENERATE_DRAFT
        )

        # Graph entry
        state_graph = StateGraph(GenerateTextState)
        state_graph.add_edge(START, first_node)

        # Outline: optional first pass at the post's shape
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
                # A rewrite is its own node so it can use its own LLM tier
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

        # Draft: always runs
        draft_node = self._node_service.build_generate_node(
            GenerateTextNodeType.GENERATE_DRAFT,
            LlmType.STRONG,
            draft_prompt,
            blog_post_body_output_format,
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
                blog_post_body_output_format,
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

        # Humanize: optional last pass over the draft
        if humanize_options is not None and humanize_options.is_enabled:
            humanize_node = self._node_service.build_generate_node(
                GenerateTextNodeType.HUMANIZE,
                LlmType.STRONG,
                humanize_prompt,
                blog_post_body_output_format,
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
                    blog_post_body_output_format,
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

        # Compile with the checkpointer
        return state_graph.compile(checkpointer=checkpointer)

    def _route_after_review(
        self,
        state: GenerateTextState,
        review_node_type: GenerateTextNodeType,
        rewrite_node_type: GenerateTextNodeType,
        next_entry: str,
    ) -> str:
        """Moves on when approved or out of rewrite passes, otherwise rewrites."""
        is_approved = (
            state.step_decisions.get(review_node_type.value) == HumanDecisionType.APPROVED.value
        )
        rewrite_count = state.rewrite_counts.get(review_node_type.value, 0)
        if is_approved or rewrite_count >= self._generate_text_settings.max_rewrite_passes:
            return next_entry
        return rewrite_node_type
