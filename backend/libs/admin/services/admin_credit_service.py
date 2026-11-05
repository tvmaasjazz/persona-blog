from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from libs.admin.exceptions import AdminCreditGrantSystemUserException
from libs.admin.inputs import GrantUserCreditsInput
from libs.admin.results import (
    CreditLedgerEntryResult,
    FindUserCreditLedgerResult,
    GrantUserCreditsResult,
)
from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.credits.inputs import GrantCreditsInput
from libs.credits.services import CreditLedgerService
from libs.database.orm import CreditLedgerOrm, GenerateTextRunOrm, RoleOrm, UserOrm
from libs.permissions.types import RoleType


class AdminCreditService:
    """Reads any user's ledger and grants them credits for the admin; the ledger rows and
    balance are written through CreditLedgerService."""

    def __init__(
        self, db_session: AsyncSession, credit_ledger_service: CreditLedgerService
    ) -> None:
        self._db_session = db_session
        self._credit_ledger_service = credit_ledger_service

    async def find_user_credit_ledger(self, user_identity: UUID) -> FindUserCreditLedgerResult:
        """The user's ledger rows, newest first, empty when they have none; NotFoundException
        for an unknown identity or the system user."""
        user_id = await self._find_user_id(user_identity)

        # A charge or refund names its run; a grant names none
        created_by_user = aliased(UserOrm)
        credit_ledger_query = (
            select(
                CreditLedgerOrm.identity,
                CreditLedgerOrm.entry_type,
                CreditLedgerOrm.amount_usd,
                CreditLedgerOrm.note,
                GenerateTextRunOrm.identity.label("generate_text_run_identity"),
                created_by_user.email.label("created_by_email"),
                CreditLedgerOrm.created_at,
            )
            .outerjoin(
                GenerateTextRunOrm, GenerateTextRunOrm.id == CreditLedgerOrm.generate_text_run_id
            )
            .join(created_by_user, created_by_user.id == CreditLedgerOrm.created_by_id)
            .where(CreditLedgerOrm.user_id == user_id)
            .order_by(CreditLedgerOrm.created_at.desc(), CreditLedgerOrm.id.desc())
        )
        credit_ledger_query_result = await self._db_session.execute(credit_ledger_query)
        credit_ledger_rows = credit_ledger_query_result.mappings().all()

        return FindUserCreditLedgerResult(
            credit_ledger_entries=[
                CreditLedgerEntryResult.model_validate(credit_ledger_row)
                for credit_ledger_row in credit_ledger_rows
            ]
        )

    async def grant_user_credits(
        self,
        user_identity: UUID,
        grant_user_credits_input: GrantUserCreditsInput,
        auth_user: AuthUser,
    ) -> GrantUserCreditsResult:
        """Grants the user credits and makes a reader a creator, saying whether it did;
        NotFoundException for an unknown identity, AdminCreditGrantSystemUserException for the
        system user."""
        # Find the user, refusing the system user, which never spends
        user_query = select(UserOrm.id, UserOrm.is_system_user).where(
            UserOrm.identity == user_identity
        )
        user_query_result = await self._db_session.execute(user_query)
        user_row = user_query_result.one_or_none()
        if user_row is None:
            raise NotFoundException("User not found")
        user_id, is_system_user = user_row
        if is_system_user:
            raise AdminCreditGrantSystemUserException("The system user can't be granted credits")

        # Grant the credits
        grant_credits_input = GrantCreditsInput(
            user_id=user_id,
            amount_usd=grant_user_credits_input.amount_usd,
            note=grant_user_credits_input.note,
        )
        grant_credits_result = await self._credit_ledger_service.grant_credits(
            grant_credits_input, auth_user
        )

        # Make a reader a creator; any other role is left alone
        reader_role_id_query = select(RoleOrm.id).where(RoleOrm.code == RoleType.READER)
        creator_role_id_query = select(RoleOrm.id).where(RoleOrm.code == RoleType.CREATOR)
        user_role_update = (
            update(UserOrm)
            .where(
                UserOrm.id == user_id,
                UserOrm.role_id == reader_role_id_query.scalar_subquery(),
            )
            .values(
                role_id=creator_role_id_query.scalar_subquery(),
                updated_by_id=auth_user.id,
            )
        )
        user_role_update_result = await self._db_session.execute(user_role_update)

        return GrantUserCreditsResult(
            identity=grant_credits_result.identity,
            user_id=user_id,
            is_made_creator=user_role_update_result.rowcount == 1,
        )

    async def _find_user_id(self, user_identity: UUID) -> int:
        user_id_query = select(UserOrm.id).where(
            UserOrm.identity == user_identity, UserOrm.is_system_user.is_(False)
        )
        user_id_query_result = await self._db_session.execute(user_id_query)
        user_id = user_id_query_result.scalar_one_or_none()

        if user_id is None:
            raise NotFoundException("User not found")
        return user_id
