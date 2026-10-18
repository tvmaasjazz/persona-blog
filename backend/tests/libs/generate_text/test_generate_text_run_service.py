from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.generate_text.results import (
    ClaimExpiredGenerateTextRunResult,
    FindGenerateTextRunByIdentityResult,
)
from libs.generate_text.services.generate_text_run_service import GenerateTextRunService
from libs.generate_text.types import GenerateTextRunStatusType, TextType
from tests.factories.auth import build_auth_user
from tests.factories.generate_text import (
    build_create_generate_text_run_input,
    insert_generate_text_run_row,
)
from tests.factories.llm import insert_llm_call_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row

EXPIRED_LEASE_EXPIRES_AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
NEW_LEASE_EXPIRES_AT = datetime(2098, 1, 2, 3, 4, 5, tzinfo=UTC)
OLD_LEASE_EXPIRES_AT = datetime(2099, 1, 2, 3, 4, 5, tzinfo=UTC)


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def _insert_persona_id(db_session: AsyncSession, *, created_by_id: int) -> int:
    persona_record = await insert_persona_row(db_session, created_by_id=created_by_id)
    await db_session.commit()
    return persona_record.id


async def test_create_run_persists_pending_row(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_generate_text_run_input = build_create_generate_text_run_input(
        graph_name="blog_post", graph_version="2026-09-24.1", persona_id=persona_id
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
    assert run_record.created_by_id == auth_user.id
    assert run_record.updated_by_id == auth_user.id
    assert run_record.created_at is not None


async def test_create_run_persists_persona_id_tone_and_target_audience(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_generate_text_run_input = build_create_generate_text_run_input(
        persona_id=persona_id, tone="Playful", target_audience="Home bakers"
    )

    create_run_result = await generate_text_run_service.create_run(
        create_generate_text_run_input, auth_user
    )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.persona_id == persona_id
    assert run_record.tone == "Playful"
    assert run_record.target_audience == "Home bakers"


async def test_start_run_sets_running_status_and_started_at(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(persona_id=persona_id), auth_user
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


async def test_complete_run_sets_completed_status_and_zero_rollup_when_no_calls(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(persona_id=persona_id), auth_user
    )

    await generate_text_run_service.complete_run(create_run_result.id)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.COMPLETED
    assert run_record.finished_at is not None
    assert run_record.llm_call_count == 0
    assert run_record.input_tokens == 0
    assert run_record.output_tokens == 0
    assert run_record.cost_usd == Decimal("0")


async def test_complete_run_sums_llm_calls_coalescing_null_tokens_and_cost(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(persona_id=persona_id), auth_user
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=auth_user.id,
        run_id=create_run_result.id,
        input_tokens=100,
        output_tokens=50,
        cost_usd=Decimal("0.01"),
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=auth_user.id,
        run_id=create_run_result.id,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
    )
    await db_session.commit()

    await generate_text_run_service.complete_run(create_run_result.id)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.llm_call_count == 2
    assert run_record.input_tokens == 100
    assert run_record.output_tokens == 50
    assert run_record.cost_usd == Decimal("0.01")


async def test_record_awaiting_review_sets_awaiting_review_status_and_rolls_up_calls(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(persona_id=persona_id), auth_user
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=auth_user.id,
        run_id=create_run_result.id,
        input_tokens=100,
        output_tokens=50,
        cost_usd=Decimal("0.01"),
    )
    await db_session.commit()

    await generate_text_run_service.record_awaiting_review(create_run_result.id)

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.AWAITING_REVIEW
    assert run_record.llm_call_count == 1
    assert run_record.input_tokens == 100
    assert run_record.output_tokens == 50
    assert run_record.cost_usd == Decimal("0.01")


async def test_fail_run_sets_failed_status_error_fields_and_rolls_up_calls(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(persona_id=persona_id), auth_user
    )
    await insert_llm_call_row(
        db_session,
        created_by_id=auth_user.id,
        run_id=create_run_result.id,
        input_tokens=100,
        output_tokens=50,
        cost_usd=Decimal("0.01"),
    )
    await db_session.commit()

    await generate_text_run_service.fail_run(create_run_result.id, "ValueError", "boom")

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "ValueError"
    assert run_record.error_message == "boom"
    assert run_record.finished_at is not None
    assert run_record.llm_call_count == 1
    assert run_record.input_tokens == 100
    assert run_record.output_tokens == 50
    assert run_record.cost_usd == Decimal("0.01")


async def test_fail_run_already_failed_keeps_first_failures_values(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_run_result = await generate_text_run_service.create_run(
        build_create_generate_text_run_input(persona_id=persona_id), auth_user
    )
    await generate_text_run_service.fail_run(create_run_result.id, "ValueError", "first failure")

    await generate_text_run_service.fail_run(create_run_result.id, "RuntimeError", "second failure")

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.FAILED
    assert run_record.error_code == "ValueError"
    assert run_record.error_message == "first failure"


async def test_find_run_by_identity_returns_result(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_record = await insert_persona_row(db_session, created_by_id=auth_user.id)
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_generate_text_run_input = build_create_generate_text_run_input(
        graph_name="blog_post",
        graph_version="2026-09-24.1",
        prompt_text="Write about sourdough starters.",
        persona_id=persona_record.id,
        tone="Playful",
        target_audience="Home bakers",
        additional_context="Mention rye flour.",
        options={"draft": {"is_enabled": True, "is_auto_approved": False}},
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
        text_type=TextType.BLOG_POST,
        graph_name="blog_post",
        graph_version="2026-09-24.1",
        status=GenerateTextRunStatusType.PENDING,
        prompt_text="Write about sourdough starters.",
        tone="Playful",
        target_audience="Home bakers",
        additional_context="Mention rye flour.",
        options={"draft": {"is_enabled": True, "is_auto_approved": False}},
        persona_id=persona_record.id,
        persona_identity=persona_record.identity,
        llm_call_count=0,
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal("0"),
        started_at=None,
        finished_at=None,
        created_by_id=auth_user.id,
    )


async def test_find_run_by_identity_null_persona_id_returns_null_persona_identity(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=auth_user.id, persona_id=None
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    find_run_result = await generate_text_run_service.find_run_by_identity(run_record.identity)

    assert find_run_result.persona_id is None
    assert find_run_result.persona_identity is None


async def test_find_run_by_identity_soft_deleted_persona_returns_null_persona_identity(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=auth_user.id,
        deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        deleted_by_id=auth_user.id,
    )
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=auth_user.id, persona_id=persona_record.id
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    find_run_result = await generate_text_run_service.find_run_by_identity(run_record.identity)

    assert find_run_result.persona_id == persona_record.id
    assert find_run_result.persona_identity is None


async def test_find_run_by_identity_not_found_raises_not_found_exception(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    with pytest.raises(NotFoundException):
        await generate_text_run_service.find_run_by_identity(uuid4())


async def test_claim_paused_run_awaiting_review_returns_true_and_sets_running(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=auth_user.id, status=GenerateTextRunStatusType.AWAITING_REVIEW
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    is_claimed = await generate_text_run_service.claim_paused_run(
        run_record.id, "new-worker", NEW_LEASE_EXPIRES_AT
    )

    await db_session.refresh(run_record)
    assert is_claimed is True
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.lease_owner == "new-worker"
    assert run_record.lease_expires_at == NEW_LEASE_EXPIRES_AT


async def test_claim_paused_run_already_claimed_returns_false(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=auth_user.id, status=GenerateTextRunStatusType.AWAITING_REVIEW
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    await generate_text_run_service.claim_paused_run(
        run_record.id, "new-worker", NEW_LEASE_EXPIRES_AT
    )

    is_claimed = await generate_text_run_service.claim_paused_run(
        run_record.id, "new-worker", NEW_LEASE_EXPIRES_AT
    )

    assert is_claimed is False


@pytest.mark.parametrize(
    "run_status",
    [
        pytest.param(GenerateTextRunStatusType.PENDING, id="pending"),
        pytest.param(GenerateTextRunStatusType.RUNNING, id="running"),
        pytest.param(GenerateTextRunStatusType.COMPLETED, id="completed"),
        pytest.param(GenerateTextRunStatusType.FAILED, id="failed"),
    ],
)
async def test_claim_paused_run_not_awaiting_review_returns_false_and_keeps_status(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    run_status: GenerateTextRunStatusType,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=auth_user.id, status=run_status
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    is_claimed = await generate_text_run_service.claim_paused_run(
        run_record.id, "new-worker", NEW_LEASE_EXPIRES_AT
    )

    await db_session.refresh(run_record)
    assert is_claimed is False
    assert run_record.status == run_status


async def test_create_run_persists_lease(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_id = await _insert_persona_id(db_session, created_by_id=auth_user.id)
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    create_generate_text_run_input = build_create_generate_text_run_input(
        persona_id=persona_id, lease_owner="creator-worker", lease_expires_at=NEW_LEASE_EXPIRES_AT
    )

    create_run_result = await generate_text_run_service.create_run(
        create_generate_text_run_input, auth_user
    )

    run_query = select(GenerateTextRunOrm).where(GenerateTextRunOrm.id == create_run_result.id)
    run_record = await db_session.scalar(run_query)
    assert run_record is not None
    assert run_record.status == GenerateTextRunStatusType.PENDING
    assert run_record.lease_owner == "creator-worker"
    assert run_record.lease_expires_at == NEW_LEASE_EXPIRES_AT


async def test_renew_lease_owner_returns_true_and_extends_lease(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="owner-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    is_renewed = await generate_text_run_service.renew_lease(
        run_record.id, "owner-worker", NEW_LEASE_EXPIRES_AT
    )

    await db_session.refresh(run_record)
    assert is_renewed is True
    assert run_record.lease_owner == "owner-worker"
    assert run_record.lease_expires_at == NEW_LEASE_EXPIRES_AT


async def test_renew_lease_non_owner_returns_false_and_keeps_lease(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="owner-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    is_renewed = await generate_text_run_service.renew_lease(
        run_record.id, "other-worker", NEW_LEASE_EXPIRES_AT
    )

    await db_session.refresh(run_record)
    assert is_renewed is False
    assert run_record.lease_owner == "owner-worker"
    assert run_record.lease_expires_at == OLD_LEASE_EXPIRES_AT


async def test_renew_lease_cleared_lease_returns_false(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session, created_by_id=auth_user.id, status=GenerateTextRunStatusType.COMPLETED
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    is_renewed = await generate_text_run_service.renew_lease(
        run_record.id, "owner-worker", NEW_LEASE_EXPIRES_AT
    )

    assert is_renewed is False


async def test_release_lease_owner_expires_lease_and_keeps_status_and_owner(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="owner-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    await generate_text_run_service.release_lease(run_record.id, "owner-worker")

    await db_session.refresh(run_record)
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.lease_owner == "owner-worker"
    assert run_record.lease_expires_at is not None
    assert run_record.lease_expires_at < OLD_LEASE_EXPIRES_AT


async def test_release_lease_non_owner_changes_nothing(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="owner-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    await generate_text_run_service.release_lease(run_record.id, "other-worker")

    await db_session.refresh(run_record)
    assert run_record.status == GenerateTextRunStatusType.RUNNING
    assert run_record.lease_owner == "owner-worker"
    assert run_record.lease_expires_at == OLD_LEASE_EXPIRES_AT


async def test_complete_run_clears_lease(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="owner-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    await generate_text_run_service.complete_run(run_record.id)

    await db_session.refresh(run_record)
    assert run_record.lease_owner is None
    assert run_record.lease_expires_at is None


async def test_record_awaiting_review_clears_lease(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="owner-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    await generate_text_run_service.record_awaiting_review(run_record.id)

    await db_session.refresh(run_record)
    assert run_record.lease_owner is None
    assert run_record.lease_expires_at is None


async def test_fail_run_clears_lease(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="owner-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    await generate_text_run_service.fail_run(run_record.id, "RuntimeError", "boom")

    await db_session.refresh(run_record)
    assert run_record.lease_owner is None
    assert run_record.lease_expires_at is None


@pytest.mark.parametrize(
    "run_status",
    [
        pytest.param(GenerateTextRunStatusType.PENDING, id="pending"),
        pytest.param(GenerateTextRunStatusType.RUNNING, id="running"),
    ],
)
async def test_claim_expired_run_expired_lease_returns_result_and_takes_lease(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    run_status: GenerateTextRunStatusType,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        graph_version="2026-09-24.1",
        status=run_status,
        options={"draft": {"is_enabled": True}},
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
        pickup_count=2,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    claim_expired_run_result = await generate_text_run_service.claim_expired_run(
        "new-worker", NEW_LEASE_EXPIRES_AT
    )

    await db_session.refresh(run_record)
    assert claim_expired_run_result == ClaimExpiredGenerateTextRunResult(
        id=run_record.id,
        identity=run_record.identity,
        status=run_status,
        pickup_count=3,
        text_type=TextType.BLOG_POST,
        graph_version="2026-09-24.1",
        options={"draft": {"is_enabled": True}},
        created_by_id=auth_user.id,
    )
    assert run_record.status == run_status
    assert run_record.lease_owner == "new-worker"
    assert run_record.lease_expires_at == NEW_LEASE_EXPIRES_AT
    assert run_record.pickup_count == 3


async def test_claim_expired_run_picks_oldest_expired_lease_only(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    newer_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    oldest_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    middle_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    claim_expired_run_result = await generate_text_run_service.claim_expired_run(
        "new-worker", NEW_LEASE_EXPIRES_AT
    )

    await db_session.refresh(newer_run_record)
    await db_session.refresh(middle_run_record)
    assert claim_expired_run_result is not None
    assert claim_expired_run_result.id == oldest_run_record.id
    assert newer_run_record.pickup_count == 0
    assert middle_run_record.pickup_count == 0


async def test_claim_expired_run_claimed_run_is_not_claimed_again(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)
    await generate_text_run_service.claim_expired_run("first-worker", NEW_LEASE_EXPIRES_AT)

    second_claim_result = await generate_text_run_service.claim_expired_run(
        "second-worker", NEW_LEASE_EXPIRES_AT
    )

    assert second_claim_result is None


async def test_claim_expired_run_nothing_in_table_returns_none(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    claim_expired_run_result = await generate_text_run_service.claim_expired_run(
        "new-worker", NEW_LEASE_EXPIRES_AT
    )

    assert claim_expired_run_result is None


@pytest.mark.parametrize(
    "run_status",
    [
        pytest.param(GenerateTextRunStatusType.AWAITING_REVIEW, id="awaiting_review"),
        pytest.param(GenerateTextRunStatusType.COMPLETED, id="completed"),
        pytest.param(GenerateTextRunStatusType.FAILED, id="failed"),
    ],
)
async def test_claim_expired_run_settled_status_returns_none_and_keeps_run(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    run_status: GenerateTextRunStatusType,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=run_status,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    claim_expired_run_result = await generate_text_run_service.claim_expired_run(
        "new-worker", NEW_LEASE_EXPIRES_AT
    )

    await db_session.refresh(run_record)
    assert claim_expired_run_result is None
    assert run_record.lease_owner == "dead-worker"
    assert run_record.pickup_count == 0


async def test_claim_expired_run_null_lease_returns_none(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    await insert_generate_text_run_row(
        db_session, created_by_id=auth_user.id, status=GenerateTextRunStatusType.RUNNING
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    claim_expired_run_result = await generate_text_run_service.claim_expired_run(
        "new-worker", NEW_LEASE_EXPIRES_AT
    )

    assert claim_expired_run_result is None


async def test_claim_expired_run_unexpired_lease_returns_none(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="live-worker",
        lease_expires_at=OLD_LEASE_EXPIRES_AT,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    claim_expired_run_result = await generate_text_run_service.claim_expired_run(
        "new-worker", NEW_LEASE_EXPIRES_AT
    )

    assert claim_expired_run_result is None


async def test_claim_expired_run_soft_deleted_run_returns_none(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    auth_user = await _insert_auth_user(db_session)
    run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=auth_user.id,
        status=GenerateTextRunStatusType.RUNNING,
        lease_owner="dead-worker",
        lease_expires_at=EXPIRED_LEASE_EXPIRES_AT,
        deleted_at=EXPIRED_LEASE_EXPIRES_AT,
        deleted_by_id=auth_user.id,
    )
    await db_session.commit()
    generate_text_run_service = GenerateTextRunService(db_session_factory=db_session_factory)

    claim_expired_run_result = await generate_text_run_service.claim_expired_run(
        "new-worker", NEW_LEASE_EXPIRES_AT
    )

    pickup_count_query = text(
        "SELECT pickup_count FROM pb_generate_text_run WHERE id = :run_id"
    ).bindparams(run_id=run_record.id)
    pickup_count_scalar = await db_session.scalar(pickup_count_query)
    assert claim_expired_run_result is None
    assert pickup_count_scalar == 0
