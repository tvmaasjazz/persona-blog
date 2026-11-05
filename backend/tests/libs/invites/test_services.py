from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.credits.services import CreditLedgerService
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm import CreditLedgerOrm, InviteOrm, RoleOrm, UserOrm
from libs.invites.exceptions import InviteNotFoundException
from libs.invites.results import FindInviteStatusResult, RedeemInviteResult
from libs.invites.services import InviteService
from libs.invites.types import InviteSignInResultType, InviteStatusType
from libs.invites.utils import InviteUtils
from libs.permissions.types import RoleType
from libs.users.services import UserService
from tests.factories.database import fetch_database_utc_now
from tests.factories.invites import insert_invite_row
from tests.factories.users import insert_user_row

PAST = datetime(2026, 1, 2, tzinfo=UTC)


@pytest.fixture
def invite_service(db_session: AsyncSession) -> InviteService:
    return InviteService(
        db_session=db_session,
        credit_ledger_service=CreditLedgerService(db_session=db_session),
        user_service=UserService(
            db_session=db_session, low_credit_balance_threshold_usd=Decimal("0.50")
        ),
    )


async def _find_role_code(db_session: AsyncSession, user_id: int) -> RoleType | None:
    role_code_query = (
        select(RoleOrm.code)
        .join(UserOrm, UserOrm.role_id == RoleOrm.id)
        .where(UserOrm.id == user_id)
    )
    return await db_session.scalar(role_code_query)


async def _count_ledger_rows(db_session: AsyncSession) -> int | None:
    ledger_count_query = select(func.count(CreditLedgerOrm.id))
    return await db_session.scalar(ledger_count_query)


# find_invite_status


async def test_find_invite_status_unused_invite_returns_unused_and_amount(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        credit_amount_usd=Decimal("7.50"),
    )

    find_invite_status_result = await invite_service.find_invite_status("known-code")

    assert find_invite_status_result == FindInviteStatusResult(
        status=InviteStatusType.UNUSED, credit_amount_usd=Decimal("7.50")
    )


async def test_find_invite_status_used_invite_returns_used(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        used_at=PAST,
        used_by_user_id=user_record.id,
    )

    find_invite_status_result = await invite_service.find_invite_status("known-code")

    assert find_invite_status_result.status == InviteStatusType.USED


async def test_find_invite_status_expired_invite_returns_expired(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code"), expires_at=PAST
    )

    find_invite_status_result = await invite_service.find_invite_status("known-code")

    assert find_invite_status_result.status == InviteStatusType.EXPIRED


async def test_find_invite_status_revoked_invite_returns_revoked(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code"), revoked_at=PAST
    )

    find_invite_status_result = await invite_service.find_invite_status("known-code")

    assert find_invite_status_result.status == InviteStatusType.REVOKED


async def test_find_invite_status_unknown_code_raises_invite_not_found_exception(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    await insert_invite_row(db_session, code_hash=InviteUtils.hash_code("known-code"))

    with pytest.raises(InviteNotFoundException):
        await invite_service.find_invite_status("another-code")


# find_invite_sign_in_refusal


async def test_find_invite_sign_in_refusal_unused_invite_returns_none(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    await insert_invite_row(db_session, code_hash=InviteUtils.hash_code("known-code"))

    invite_sign_in_refusal = await invite_service.find_invite_sign_in_refusal("known-code")

    assert invite_sign_in_refusal is None


async def test_find_invite_sign_in_refusal_used_invite_returns_invite_used(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(db_session)
    await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        used_at=PAST,
        used_by_user_id=user_record.id,
    )

    invite_sign_in_refusal = await invite_service.find_invite_sign_in_refusal("known-code")

    assert invite_sign_in_refusal == InviteSignInResultType.INVITE_USED


async def test_find_invite_sign_in_refusal_expired_invite_returns_invite_expired(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code"), expires_at=PAST
    )

    invite_sign_in_refusal = await invite_service.find_invite_sign_in_refusal("known-code")

    assert invite_sign_in_refusal == InviteSignInResultType.INVITE_EXPIRED


async def test_find_invite_sign_in_refusal_revoked_invite_returns_invite_revoked(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code"), revoked_at=PAST
    )

    invite_sign_in_refusal = await invite_service.find_invite_sign_in_refusal("known-code")

    assert invite_sign_in_refusal == InviteSignInResultType.INVITE_REVOKED


async def test_find_invite_sign_in_refusal_unknown_code_returns_invite_not_found(
    invite_service: InviteService,
) -> None:
    invite_sign_in_refusal = await invite_service.find_invite_sign_in_refusal("unknown-code")

    assert invite_sign_in_refusal == InviteSignInResultType.INVITE_NOT_FOUND


# redeem_invite


async def test_redeem_invite_unused_invite_returns_accepted_and_marks_invite_used(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    invite_record = await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code")
    )

    redeem_invite_result = await invite_service.redeem_invite("known-code", user_record.id)

    await db_session.refresh(invite_record)
    database_utc_now = await fetch_database_utc_now(db_session)
    assert redeem_invite_result == RedeemInviteResult(
        result_type=InviteSignInResultType.ACCEPTED, is_made_creator=True
    )
    assert invite_record.used_at == database_utc_now
    assert invite_record.used_by_user_id == user_record.id


async def test_redeem_invite_reader_becomes_creator_updated_by_the_invites_author(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    invite_record = await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code")
    )

    await invite_service.redeem_invite("known-code", user_record.id)

    role_code = await _find_role_code(db_session, user_record.id)
    updated_by_id_query = select(UserOrm.updated_by_id).where(UserOrm.id == user_record.id)
    updated_by_id = await db_session.scalar(updated_by_id_query)
    assert role_code == RoleType.CREATOR
    assert updated_by_id == invite_record.created_by_id


@pytest.mark.parametrize("role", [RoleType.CREATOR, RoleType.ADMIN])
async def test_redeem_invite_creator_or_admin_keeps_role(
    db_session: AsyncSession, invite_service: InviteService, role: RoleType
) -> None:
    user_record = await insert_user_row(db_session, role=role)
    await insert_invite_row(db_session, code_hash=InviteUtils.hash_code("known-code"))

    redeem_invite_result = await invite_service.redeem_invite("known-code", user_record.id)

    role_code = await _find_role_code(db_session, user_record.id)
    assert redeem_invite_result == RedeemInviteResult(
        result_type=InviteSignInResultType.ACCEPTED, is_made_creator=False
    )
    assert role_code == role


async def test_redeem_invite_grants_credits_with_invite_note_authored_by_invites_creator(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(
        db_session, role=RoleType.READER, credit_balance_usd=Decimal("1.00")
    )
    invite_record = await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        credit_amount_usd=Decimal("7.50"),
        note="Welcome to the beta",
    )

    await invite_service.redeem_invite("known-code", user_record.id)

    await db_session.refresh(user_record)
    ledger_query = select(CreditLedgerOrm).where(CreditLedgerOrm.user_id == user_record.id)
    ledger_record = await db_session.scalar(ledger_query)
    assert ledger_record is not None
    assert ledger_record.entry_type == CreditLedgerEntryType.GRANT
    assert ledger_record.amount_usd == Decimal("7.50")
    assert ledger_record.note == "Welcome to the beta"
    assert ledger_record.invite_id == invite_record.id
    assert ledger_record.created_by_id == invite_record.created_by_id
    assert user_record.credit_balance_usd == Decimal("8.50")


async def test_redeem_invite_without_note_grants_credits_with_invite_name_note(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code"), name="Ada's friends", note=None
    )

    await invite_service.redeem_invite("known-code", user_record.id)

    note_query = select(CreditLedgerOrm.note).where(CreditLedgerOrm.user_id == user_record.id)
    ledger_note = await db_session.scalar(note_query)
    assert ledger_note == "Invite: Ada's friends"


@pytest.mark.parametrize(
    ("invite_used", "invite_expired", "invite_revoked", "expected_result_type"),
    [
        pytest.param(True, False, False, InviteSignInResultType.INVITE_USED, id="used"),
        pytest.param(False, True, False, InviteSignInResultType.INVITE_EXPIRED, id="expired"),
        pytest.param(False, False, True, InviteSignInResultType.INVITE_REVOKED, id="revoked"),
    ],
)
async def test_redeem_invite_unusable_invite_returns_reason_and_writes_nothing(
    db_session: AsyncSession,
    invite_service: InviteService,
    invite_used: bool,
    invite_expired: bool,
    invite_revoked: bool,
    expected_result_type: InviteSignInResultType,
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    previous_user_record = await insert_user_row(db_session)
    invite_record = await insert_invite_row(
        db_session,
        code_hash=InviteUtils.hash_code("known-code"),
        used_at=PAST if invite_used else None,
        used_by_user_id=previous_user_record.id if invite_used else None,
        expires_at=PAST if invite_expired else datetime(2099, 1, 1, tzinfo=UTC),
        revoked_at=PAST if invite_revoked else None,
    )

    redeem_invite_result = await invite_service.redeem_invite("known-code", user_record.id)

    await db_session.refresh(invite_record)
    await db_session.refresh(user_record)
    role_code = await _find_role_code(db_session, user_record.id)
    ledger_row_count = await _count_ledger_rows(db_session)
    assert redeem_invite_result == RedeemInviteResult(
        result_type=expected_result_type, is_made_creator=False
    )
    assert invite_record.used_by_user_id == (previous_user_record.id if invite_used else None)
    assert role_code == RoleType.READER
    assert user_record.credit_balance_usd == Decimal(0)
    assert ledger_row_count == 0


async def test_redeem_invite_unknown_code_returns_invite_not_found_and_writes_nothing(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    invite_record = await insert_invite_row(db_session)

    redeem_invite_result = await invite_service.redeem_invite("unknown-code", user_record.id)

    await db_session.refresh(invite_record)
    role_code = await _find_role_code(db_session, user_record.id)
    ledger_row_count = await _count_ledger_rows(db_session)
    assert redeem_invite_result == RedeemInviteResult(
        result_type=InviteSignInResultType.INVITE_NOT_FOUND, is_made_creator=False
    )
    assert invite_record.used_at is None
    assert role_code == RoleType.READER
    assert ledger_row_count == 0


async def test_redeem_invite_twice_second_returns_invite_used_with_one_ledger_row(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    first_user_record = await insert_user_row(db_session, role=RoleType.READER)
    second_user_record = await insert_user_row(db_session, role=RoleType.READER)
    invite_record = await insert_invite_row(
        db_session, code_hash=InviteUtils.hash_code("known-code")
    )
    await invite_service.redeem_invite("known-code", first_user_record.id)

    second_redeem_invite_result = await invite_service.redeem_invite(
        "known-code", second_user_record.id
    )

    await db_session.refresh(invite_record)
    second_role_code = await _find_role_code(db_session, second_user_record.id)
    ledger_row_count = await _count_ledger_rows(db_session)
    assert second_redeem_invite_result == RedeemInviteResult(
        result_type=InviteSignInResultType.INVITE_USED, is_made_creator=False
    )
    assert invite_record.used_by_user_id == first_user_record.id
    assert second_role_code == RoleType.READER
    assert ledger_row_count == 1


async def test_redeem_invite_code_stored_unhashed_returns_invite_not_found(
    db_session: AsyncSession, invite_service: InviteService
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.READER)
    await insert_invite_row(db_session, code_hash="known-code")

    redeem_invite_result = await invite_service.redeem_invite("known-code", user_record.id)

    invite_count_query = select(func.count(InviteOrm.id)).where(InviteOrm.used_at.is_not(None))
    used_invite_count = await db_session.scalar(invite_count_query)
    assert redeem_invite_result.result_type == InviteSignInResultType.INVITE_NOT_FOUND
    assert used_invite_count == 0
