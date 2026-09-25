from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.generate_text.results import FindGenerateTextRunByIdentityResult, GenerateTextRollupResult
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.types import GenerateTextRunStatusType, TextType
from tests.factories.auth import build_auth_user
from tests.factories.generate_text import build_create_generate_text_run_input
from tests.factories.users import insert_user_row


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def test_create_run_persists_pending_row(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_generate_text_run_input = build_create_generate_text_run_input(
        graph_name="blog_post", graph_version="2026-09-24.1", thread_id="thread-create"
    )

    create_run_result = await generate_text_run_service.create_run(
        create_generate_text_run_input, auth_user
    )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.identity == create_run_result.identity
    assert run_record.status == GenerateTextRunStatusType.PENDING
    assert run_record.text_type == TextType.BLOG_POST
    assert run_record.graph_name == "blog_post"
    assert run_record.graph_version == "2026-09-24.1"
    assert run_record.thread_id == "thread-create"
    assert run_record.created_by_id == auth_user.id
    assert run_record.updated_by_id == auth_user.id
    assert run_record.created_at is not None


async def test_start_run_sets_running_status_and_started_at(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )

    await generate_text_run_service.start_run(create_run_result.id)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.started_at is not None


async def test_start_run_unknown_run_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    with pytest.raises(NotFoundException):
        await generate_text_run_service.start_run(999999)


async def test_record_current_step_sets_current_step(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )

    await generate_text_run_service.record_current_step(create_run_result.id, "GENERATE_DRAFT")

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.current_step == "GENERATE_DRAFT"


async def test_complete_run_sets_completed_status_and_finished_at(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )

    await generate_text_run_service.complete_run(create_run_result.id)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.COMPLETED
    assert run_record.finished_at is not None


async def test_record_awaiting_review_sets_awaiting_review_status(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )

    await generate_text_run_service.record_awaiting_review(create_run_result.id)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.AWAITING_REVIEW


async def test_fail_run_sets_failed_status_and_error_fields(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )

    await generate_text_run_service.fail_run(
        create_run_result.id, "ValueError", "boom", "GENERATE_DRAFT"
    )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "ValueError"
    assert run_record.error_message == "boom"
    assert run_record.error_step == "GENERATE_DRAFT"
    assert run_record.finished_at is not None


async def test_record_rollup_updates_run_rollup_columns(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(), auth_user
    )
    rollup_result = GenerateTextRollupResult(
        llm_call_count=3, input_tokens=300, output_tokens=120, cost_usd=Decimal("0.045")
    )

    await generate_text_run_service.record_rollup(create_run_result.id, rollup_result)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.llm_call_count == 3
    assert run_record.input_tokens == 300
    assert run_record.output_tokens == 120
    assert run_record.cost_usd == Decimal("0.045")


async def test_find_run_by_identity_returns_result(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_generate_text_run_input = build_create_generate_text_run_input(
        graph_name="blog_post", graph_version="2026-09-24.1", thread_id="thread-find"
    )
    create_run_result = await generate_text_run_service.create_run(
        create_generate_text_run_input, auth_user
    )

    find_run_result = await generate_text_run_service.find_run_by_identity(
        create_run_result.identity
    )

    assert find_run_result == FindGenerateTextRunByIdentityResult(
        id=create_run_result.id,
        identity=create_run_result.identity,
        thread_id="thread-find",
        text_type=TextType.BLOG_POST,
        graph_name="blog_post",
        graph_version="2026-09-24.1",
        status=GenerateTextRunStatusType.PENDING,
        current_step=None,
        options={},
        llm_call_count=0,
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal("0"),
        started_at=None,
        finished_at=None,
        created_by_id=auth_user.id,
    )


async def test_find_run_by_identity_not_found_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    with pytest.raises(NotFoundException):
        await generate_text_run_service.find_run_by_identity(uuid4())
