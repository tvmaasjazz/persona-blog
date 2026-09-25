import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.blog_post.graphs import build_blog_post_graph_spec
from libs.generate_text.services.generate_text_graph_service import GenerateTextGraphService
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.services.generate_text_rollup_service import GenerateTextRollupService
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import TextType
from tests.stubs.llm import LlmServiceStub


def _build_graph_service(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> GenerateTextGraphService:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    rollup_service = GenerateTextRollupService(db_session_factory=db_session_factory)
    instrumentation_service = GenerateTextInstrumentationService(
        run_service=run_service, step_service=step_service, rollup_service=rollup_service
    )
    node_service = GenerateTextNodeService(llm_service=LlmServiceStub())
    return GenerateTextGraphService(
        generate_text_graph_specs={
            TextType.BLOG_POST: build_blog_post_graph_spec(
                node_service=node_service,
                instrumentation_service=instrumentation_service,
                generate_text_settings=GenerateTextSettings(),
            )
        }
    )


@pytest.mark.parametrize("text_type", list(TextType))
def test_build_graph_resolves_a_builder_for_every_text_type(
    text_type: TextType, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    generate_text_graph_service = _build_graph_service(db_session_factory)
    current_graph_version = generate_text_graph_service.current_graph_version(text_type)

    compiled_graph = generate_text_graph_service.build_graph(
        text_type, current_graph_version, {}, InMemorySaver()
    )

    assert compiled_graph is not None


def test_build_graph_version_mismatch_raises_not_implemented_error(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    generate_text_graph_service = _build_graph_service(db_session_factory)

    with pytest.raises(NotImplementedError):
        generate_text_graph_service.build_graph(
            TextType.BLOG_POST, "not-a-real-version", {}, InMemorySaver()
        )
