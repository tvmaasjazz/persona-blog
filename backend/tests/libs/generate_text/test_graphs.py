from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from libs.generate_text.graphs import build_generate_text_graph
from libs.generate_text.services import GenerateTextNodeService
from libs.generate_text.settings import GenerateTextSettings
from tests.factories.generate_text import build_generate_text_state
from tests.factories.llm import build_llm_completion_result
from tests.stubs.llm import LlmServiceStub


async def test_generate_text_graph_pauses_at_review_with_draft() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_node_service = GenerateTextNodeService(llm_service=llm_service_stub)
    generate_text_graph = build_generate_text_graph(
        generate_text_node_service=generate_text_node_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": "test-thread"}}
    generate_text_state = build_generate_text_state(prompt_text="Write about coffee.")

    await generate_text_graph.ainvoke(generate_text_state, graph_run_config)

    graph_state_snapshot = await generate_text_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == ("REVIEW_BLOG_POST",)
    assert graph_state_snapshot.interrupts[0].value == {
        "draft_text": "A draft about coffee.",
        "rewrite_count": 0,
    }


async def test_generate_text_graph_rejection_routes_to_rewrite_and_pauses_again() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_node_service = GenerateTextNodeService(llm_service=llm_service_stub)
    generate_text_graph = build_generate_text_graph(
        generate_text_node_service=generate_text_node_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": "test-thread"}}
    generate_text_state = build_generate_text_state(prompt_text="Write about coffee.")
    await generate_text_graph.ainvoke(generate_text_state, graph_run_config)

    llm_service_stub.complete_result = build_llm_completion_result(content="A revised draft.")
    await generate_text_graph.ainvoke(
        Command(resume={"is_approved": False, "feedback_text": "Make it shorter."}),
        graph_run_config,
    )

    graph_state_snapshot = await generate_text_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == ("REVIEW_BLOG_POST",)
    assert graph_state_snapshot.values["draft_text"] == "A revised draft."
    assert graph_state_snapshot.values["rewrite_count"] == 1


async def test_generate_text_graph_approval_ends_run() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_node_service = GenerateTextNodeService(llm_service=llm_service_stub)
    generate_text_graph = build_generate_text_graph(
        generate_text_node_service=generate_text_node_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": "test-thread"}}
    generate_text_state = build_generate_text_state(prompt_text="Write about coffee.")
    await generate_text_graph.ainvoke(generate_text_state, graph_run_config)

    await generate_text_graph.ainvoke(
        Command(resume={"is_approved": True, "feedback_text": None}), graph_run_config
    )

    graph_state_snapshot = await generate_text_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == ()
    assert graph_state_snapshot.values["draft_text"] == "A draft about coffee."


async def test_generate_text_graph_max_rewrite_passes_ends_run_instead_of_rewriting_again() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_node_service = GenerateTextNodeService(llm_service=llm_service_stub)
    generate_text_graph = build_generate_text_graph(
        generate_text_node_service=generate_text_node_service,
        generate_text_settings=GenerateTextSettings(max_rewrite_passes=1),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": "test-thread"}}
    generate_text_state = build_generate_text_state(prompt_text="Write about coffee.")
    await generate_text_graph.ainvoke(generate_text_state, graph_run_config)
    await generate_text_graph.ainvoke(
        Command(resume={"is_approved": False, "feedback_text": "Try again."}), graph_run_config
    )

    await generate_text_graph.ainvoke(
        Command(resume={"is_approved": False, "feedback_text": "Try again."}), graph_run_config
    )

    graph_state_snapshot = await generate_text_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == ()
    assert graph_state_snapshot.values["rewrite_count"] == 1
