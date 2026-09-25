from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.blog_post.graph_builder import BlogPostGraphBuilder
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import TextType


class GenerateTextGraphBuilderRegistry:
    """Maps a text type to the builder that knows how to build its graph, the enum
    dispatch pattern (python-naming.md > Enum dispatch). Every builder is constructed
    here, in __init__, so the engine never imports a text type's graph module anywhere
    else — a new text type is a new entry in the map below."""

    def __init__(
        self,
        node_service: GenerateTextNodeService,
        instrumentation_service: GenerateTextInstrumentationService,
        generate_text_settings: GenerateTextSettings,
    ) -> None:
        self._builder_by_text_type: dict[TextType, BaseGenerateTextGraphBuilder] = {
            TextType.BLOG_POST: BlogPostGraphBuilder(
                node_service, instrumentation_service, generate_text_settings
            ),
        }

    def get_by_text_type(self, text_type: TextType) -> BaseGenerateTextGraphBuilder:
        graph_builder = self._builder_by_text_type.get(text_type)
        if graph_builder is None:
            raise NotImplementedError(f"No graph builder registered for {text_type}")
        return graph_builder
