import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.generate_text.graphs.base_generate_text_graph_builder import BaseGenerateTextGraphBuilder
from libs.generate_text.graphs.generate_text_graph_builder_registry import (
    GenerateTextGraphBuilderRegistry,
)
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import TextType
from tests.stubs.llm import LlmServiceStub


def _build_registry(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> GenerateTextGraphBuilderRegistry:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    instrumentation_service = GenerateTextInstrumentationService(
        run_service=run_service, step_service=step_service
    )
    generate_text_settings = GenerateTextSettings()
    node_service = GenerateTextNodeService(
        llm_service=LlmServiceStub(), generate_text_settings=generate_text_settings
    )
    return GenerateTextGraphBuilderRegistry(
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=generate_text_settings,
    )


@pytest.mark.parametrize("text_type", list(TextType))
def test_get_by_text_type_resolves_a_builder_for_every_text_type(
    text_type: TextType, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    generate_text_graph_builder_registry = _build_registry(db_session_factory)

    graph_builder = generate_text_graph_builder_registry.get_by_text_type(text_type)

    assert isinstance(graph_builder, BaseGenerateTextGraphBuilder)
