from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.blog_post.graphs import build_blog_post_graph
from libs.generate_text.inputs import StepOptionInput
from libs.generate_text.services.generate_text_instrumentation_service import (
    GenerateTextInstrumentationService,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.services.generate_text_rollup_service import GenerateTextRollupService
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.services.generate_text_step_service import GenerateTextStepService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.states import GenerateTextState
from libs.generate_text.types import GenerateTextNodeType
from libs.llm.types import LlmType
from tests.factories.auth import build_auth_user
from tests.factories.blog_post import build_blog_post_options_input
from tests.factories.generate_text import (
    build_create_generate_text_run_input,
    build_generate_text_state,
)
from tests.factories.llm import build_llm_completion_result
from tests.factories.users import insert_user_row
from tests.stubs.llm import LlmServiceStub


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


def _build_services(
    db_session_factory: async_sessionmaker[AsyncSession], llm_service_stub: LlmServiceStub
) -> tuple[GenerateTextRunService, GenerateTextNodeService, GenerateTextInstrumentationService]:
    run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    step_service = GenerateTextStepService(db_session_factory=db_session_factory)
    rollup_service = GenerateTextRollupService(db_session_factory=db_session_factory)
    instrumentation_service = GenerateTextInstrumentationService(
        run_service=run_service, step_service=step_service, rollup_service=rollup_service
    )
    node_service = GenerateTextNodeService(llm_service=llm_service_stub)
    return run_service, node_service, instrumentation_service


async def _seed_state(
    db_session: AsyncSession, run_service: GenerateTextRunService, auth_user: AuthUser
) -> GenerateTextState:
    create_generate_text_run_input = build_create_generate_text_run_input(
        prompt_text="Write about sourdough starters."
    )
    create_run_result = await run_service.create_run(create_generate_text_run_input, auth_user)
    return build_generate_text_state(
        auth_user_id=auth_user.id,
        auth_user_identity=auth_user.identity,
        generate_text_run_id=create_run_result.id,
        generate_text_run_identity=create_run_result.identity,
        prompt_text="Write about sourdough starters.",
    )


async def test_build_blog_post_graph_all_steps_auto_approved_runs_to_end(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="Generated text.")
    run_service, node_service, instrumentation_service = _build_services(
        db_session_factory, llm_service_stub
    )
    generate_text_state = await _seed_state(db_session, run_service, auth_user)
    options = build_blog_post_options_input(
        outline=StepOptionInput(is_enabled=True, is_auto_approved=True),
        draft=StepOptionInput(is_auto_approved=True),
        humanize=StepOptionInput(is_enabled=True, is_auto_approved=True),
    )
    blog_post_graph = build_blog_post_graph(
        options=options,
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": str(uuid4())}}

    await blog_post_graph.ainvoke(generate_text_state, graph_run_config)

    graph_state_snapshot = await blog_post_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == ()
    assert graph_state_snapshot.values["step_outputs"] == {
        "GENERATE_OUTLINE": "Generated text.",
        "GENERATE_DRAFT": "Generated text.",
        "HUMANIZE": "Generated text.",
    }
    completion_llm_types = [
        completion_input.llm_type for completion_input in llm_service_stub.complete_inputs
    ]
    assert completion_llm_types == [LlmType.FAST, LlmType.STRONG, LlmType.STRONG]
    outline_completion_input = llm_service_stub.complete_inputs[0]
    assert "Write about sourdough starters." in outline_completion_input.user_prompt
    assert outline_completion_input.run_id == generate_text_state.generate_text_run_id
    assert outline_completion_input.step_id is not None


async def test_build_blog_post_graph_step_not_auto_approved_pauses_at_review(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft.")
    run_service, node_service, instrumentation_service = _build_services(
        db_session_factory, llm_service_stub
    )
    generate_text_state = await _seed_state(db_session, run_service, auth_user)
    options = build_blog_post_options_input(draft=StepOptionInput(is_auto_approved=False))
    blog_post_graph = build_blog_post_graph(
        options=options,
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": str(uuid4())}}

    await blog_post_graph.ainvoke(generate_text_state, graph_run_config)

    graph_state_snapshot = await blog_post_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == (GenerateTextNodeType.REVIEW_DRAFT.value,)
    assert graph_state_snapshot.interrupts[0].value == {"step_output": "A draft."}


async def test_build_blog_post_graph_rejection_routes_to_rewrite_and_pauses_again(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft.")
    run_service, node_service, instrumentation_service = _build_services(
        db_session_factory, llm_service_stub
    )
    generate_text_state = await _seed_state(db_session, run_service, auth_user)
    options = build_blog_post_options_input(draft=StepOptionInput(is_auto_approved=False))
    blog_post_graph = build_blog_post_graph(
        options=options,
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": str(uuid4())}}
    await blog_post_graph.ainvoke(generate_text_state, graph_run_config)

    llm_service_stub.complete_result = build_llm_completion_result(content="A revised draft.")
    resume_command = Command(resume={"is_approved": False, "feedback_text": "Make it shorter."})
    await blog_post_graph.ainvoke(resume_command, graph_run_config)

    graph_state_snapshot = await blog_post_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == (GenerateTextNodeType.REVIEW_DRAFT.value,)
    assert graph_state_snapshot.values["step_outputs"]["REWRITE_DRAFT"] == "A revised draft."
    assert graph_state_snapshot.values["rewrite_counts"]["REVIEW_DRAFT"] == 1


async def test_build_blog_post_graph_max_rewrite_passes_ends_run_instead_of_looping(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft.")
    run_service, node_service, instrumentation_service = _build_services(
        db_session_factory, llm_service_stub
    )
    generate_text_state = await _seed_state(db_session, run_service, auth_user)
    options = build_blog_post_options_input(draft=StepOptionInput(is_auto_approved=False))
    blog_post_graph = build_blog_post_graph(
        options=options,
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=GenerateTextSettings(max_rewrite_passes=1),
        checkpointer=InMemorySaver(),
    )
    graph_run_config = {"configurable": {"thread_id": str(uuid4())}}
    await blog_post_graph.ainvoke(generate_text_state, graph_run_config)
    retry_command = Command(resume={"is_approved": False, "feedback_text": "Try again."})
    await blog_post_graph.ainvoke(retry_command, graph_run_config)

    await blog_post_graph.ainvoke(retry_command, graph_run_config)

    graph_state_snapshot = await blog_post_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.next == ()
    assert graph_state_snapshot.values["rewrite_counts"]["REVIEW_DRAFT"] == 1


def test_build_blog_post_graph_outline_and_humanize_disabled_omits_their_nodes(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    llm_service_stub = LlmServiceStub()
    _, node_service, instrumentation_service = _build_services(db_session_factory, llm_service_stub)
    options = build_blog_post_options_input(draft=StepOptionInput(is_auto_approved=True))

    blog_post_graph = build_blog_post_graph(
        options=options,
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )

    assert set(blog_post_graph.nodes.keys()) == {
        "__start__",
        GenerateTextNodeType.GENERATE_DRAFT.value,
    }


def test_build_blog_post_graph_outline_enabled_not_auto_approved_adds_review_and_rewrite_nodes(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    llm_service_stub = LlmServiceStub()
    _, node_service, instrumentation_service = _build_services(db_session_factory, llm_service_stub)
    options = build_blog_post_options_input(
        outline=StepOptionInput(is_enabled=True, is_auto_approved=False),
        draft=StepOptionInput(is_auto_approved=True),
    )

    blog_post_graph = build_blog_post_graph(
        options=options,
        node_service=node_service,
        instrumentation_service=instrumentation_service,
        generate_text_settings=GenerateTextSettings(),
        checkpointer=InMemorySaver(),
    )

    assert set(blog_post_graph.nodes.keys()) == {
        "__start__",
        GenerateTextNodeType.GENERATE_OUTLINE.value,
        GenerateTextNodeType.REVIEW_OUTLINE.value,
        GenerateTextNodeType.REWRITE_OUTLINE.value,
        GenerateTextNodeType.GENERATE_DRAFT.value,
    }
