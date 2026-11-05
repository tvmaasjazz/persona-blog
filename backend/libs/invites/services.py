from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.credits.inputs import GrantCreditsInput
from libs.credits.services import CreditLedgerService
from libs.database.orm import InviteOrm
from libs.database.utils import DatabaseClockUtils
from libs.invites.exceptions import InviteNotFoundException
from libs.invites.results import FindInviteStatusResult, RedeemInviteResult
from libs.invites.types import InviteSignInResultType
from libs.invites.utils import InviteUtils
from libs.users.services import UserService


class InviteService:
    """Checks an invite code and redeems it for a signing-in user, granting its credits."""

    def __init__(
        self,
        db_session: AsyncSession,
        credit_ledger_service: CreditLedgerService,
        user_service: UserService,
    ) -> None:
        self._db_session = db_session
        self._credit_ledger_service = credit_ledger_service
        self._user_service = user_service

    async def find_invite_status(self, code: str) -> FindInviteStatusResult:
        """The code's status and credit amount; InviteNotFoundException for an unknown code."""
        code_hash = InviteUtils.hash_code(code)
        invite_query = select(
            InviteOrm.credit_amount_usd,
            InviteOrm.used_at,
            InviteOrm.revoked_at,
            (InviteOrm.expires_at <= DatabaseClockUtils.build_utc_now_sql()).label("is_expired"),
        ).where(InviteOrm.code_hash == code_hash)
        invite_query_result = await self._db_session.execute(invite_query)
        invite_row = invite_query_result.one_or_none()

        if invite_row is None:
            raise InviteNotFoundException("Invite not found")
        status_type = InviteUtils.build_status_type(
            invite_row.revoked_at, invite_row.used_at, invite_row.is_expired
        )
        return FindInviteStatusResult(
            status=status_type, credit_amount_usd=invite_row.credit_amount_usd
        )

    async def redeem_invite(self, code: str, user_id: int) -> RedeemInviteResult:
        """Marks the invite used by the user, makes a reader a creator and grants the credits,
        all on the caller's transaction; a code that can't be used changes nothing and says why."""
        # Use the invite once: the conditions are in the update, so a second use matches no row
        code_hash = InviteUtils.hash_code(code)
        invite_update = (
            update(InviteOrm)
            .where(
                InviteOrm.code_hash == code_hash,
                InviteOrm.used_at.is_(None),
                InviteOrm.revoked_at.is_(None),
                InviteOrm.expires_at > DatabaseClockUtils.build_utc_now_sql(),
            )
            .values(
                used_at=DatabaseClockUtils.build_utc_now_sql(),
                used_by_user_id=user_id,
                updated_by_id=user_id,
            )
            .returning(
                InviteOrm.id,
                InviteOrm.name,
                InviteOrm.credit_amount_usd,
                InviteOrm.note,
                InviteOrm.created_by_id,
            )
        )
        invite_update_result = await self._db_session.execute(invite_update)
        invite_row = invite_update_result.one_or_none()

        # Say why a code that matched no row can't be used
        if invite_row is None:
            return await self._build_refused_result(code)

        # Make a reader a creator, as the admin who made the invite
        is_made_creator = await self._user_service.make_reader_creator(
            user_id, invite_row.created_by_id
        )

        # Grant the credits, authored by the admin who made the invite
        grant_credits_input = GrantCreditsInput(
            user_id=user_id,
            amount_usd=invite_row.credit_amount_usd,
            note=invite_row.note or f"Invite: {invite_row.name}",
            invite_id=invite_row.id,
        )
        await self._credit_ledger_service.grant_credits(
            grant_credits_input, invite_row.created_by_id
        )

        return RedeemInviteResult(
            result_type=InviteSignInResultType.ACCEPTED, is_made_creator=is_made_creator
        )

    async def _build_refused_result(self, code: str) -> RedeemInviteResult:
        try:
            find_invite_status_result = await self.find_invite_status(code)
        except InviteNotFoundException:
            return RedeemInviteResult(
                result_type=InviteSignInResultType.INVITE_NOT_FOUND, is_made_creator=False
            )
        # An update that matched no row never leaves the invite UNUSED, for which this raises
        sign_in_result_type = InviteUtils.build_sign_in_result_type(
            find_invite_status_result.status
        )
        return RedeemInviteResult(result_type=sign_in_result_type, is_made_creator=False)
