import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from libs.generate_text.graphs import build_generate_text_graph
from libs.generate_text.services import GenerateTextService
from libs.generate_text.settings import GenerateTextSettings
from tests.stubs.llm import LlmServiceStub


@pytest.fixture
def llm_service_stub() -> LlmServiceStub:
    return LlmServiceStub()


@pytest.fixture
def generate_text_graph(llm_service_stub: LlmServiceStub) -> CompiledStateGraph:
    return build_generate_text_graph(
        llm_service=llm_service_stub,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )


@pytest.fixture
def generate_text_service(generate_text_graph: CompiledStateGraph) -> GenerateTextService:
    return GenerateTextService(generate_text_graph)
