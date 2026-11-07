from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from libs.admin.constants import ADMIN_CREDIT_LEDGER_PAGINATION_CONFIG
from libs.admin.exceptions import AdminCreditGrantSystemUserException
from libs.admin.inputs import AdminFindUserCreditLedgerPageInput, AdminGrantUserCreditsInput
from libs.admin.results import (
    AdminCreditLedgerEntryResult,
    AdminFindUserCreditLedgerPageResult,
    AdminGrantUserCreditsResult,
)
from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.credits.inputs import GrantCreditsInput
from libs.credits.services import CreditLedgerService
from libs.database.orm import CreditLedgerOrm, GenerateTextRunOrm, UserOrm
from libs.database.services import PaginationService
from libs.users.services import UserService


class AdminCreditService:
    """Reads any user's ledger and grants them credits for the admin; the ledger rows and
    balance are written through CreditLedgerService."""

    def __init__(
        self,
        db_session: AsyncSession,
        credit_ledger_service: CreditLedgerService,
        user_service: UserService,
        pagination_service: PaginationService,
    ) -> None:
        self._db_session = db_session
        self._pagination_service = pagination_service
        self._credit_ledger_service = credit_ledger_service
        self._user_service = user_service

    async def find_user_credit_ledger_page(
        self,
        user_identity: UUID,
        admin_find_user_credit_ledger_page_input: AdminFindUserCreditLedgerPageInput,
    ) -> AdminFindUserCreditLedgerPageResult:
        """One page of the user's ledger rows, searched and sorted per the input, empty when
        they have none; NotFoundException for an unknown identity or the system user."""
        user_id = await self._find_user_id(user_identity)

        # A charge or refund names its run; a grant names none. find_mapping_page searches,
        # sorts and pages the user's rows
        created_by_user = aliased(UserOrm)
        all_records_query = (
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
        )
        find_page_result = await self._pagination_service.find_mapping_page(
            all_records_query,
            ADMIN_CREDIT_LEDGER_PAGINATION_CONFIG,
            admin_find_user_credit_ledger_page_input,
        )

        return AdminFindUserCreditLedgerPageResult(
            credit_ledger_entries=[
                AdminCreditLedgerEntryResult.model_validate(credit_ledger_record)
                for credit_ledger_record in find_page_result.records
            ],
            pagination=find_page_result.pagination,
        )

    async def grant_user_credits(
        self,
        user_identity: UUID,
        grant_user_credits_input: AdminGrantUserCreditsInput,
        auth_user: AuthUser,
    ) -> AdminGrantUserCreditsResult:
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
            grant_credits_input, auth_user.id
        )

        # Make a reader a creator; any other role is left alone
        is_made_creator = await self._user_service.make_reader_creator(user_id, auth_user.id)

        return AdminGrantUserCreditsResult(
            identity=grant_credits_result.identity,
            user_id=user_id,
            is_made_creator=is_made_creator,
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
