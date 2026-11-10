"""Fills a local development database once with every case the frontend screens show.

Run from backend/ against the database in .env:

    uv run python -m scripts.dev_seed

Safe to run again: a user, invite or persona it already added is skipped. No LLM calls.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.core.config import AppSettings
from libs.admin.inputs import (
    AdminCreateInviteInput,
    AdminGrantUserCreditsInput,
    AdminSetUserActiveInput,
    AdminSetUserRoleInput,
)
from libs.admin.results import AdminCreateInviteResult
from libs.admin.services import AdminCreditService, AdminInviteService, AdminUserService
from libs.auth.results import AuthUser
from libs.auth.types import AuthProviderType
from libs.blog_posts.inputs import CreateBlogPostInput
from libs.blog_posts.services import BlogPostService
from libs.content_engagement.services import ContentEngagementService
from libs.content_items.services import ContentItemService
from libs.credits.services import CreditLedgerService
from libs.credits.types import CreditLedgerEntryType
from libs.database.orm import CreditLedgerOrm, InviteOrm, RoleOrm, UserOrm
from libs.database.services import PaginationService
from libs.database.session import create_db_session_factory
from libs.database.utils import DatabaseClockUtils
from libs.generate_text.services import GenerateTextRunService, GenerateTextStepService
from libs.invites.services import InviteService
from libs.invites.types import InviteSignInResultType
from libs.permissions.services import PermissionService
from libs.permissions.types import RoleType
from libs.personas.inputs import PersonaInput
from libs.personas.services import PersonaService
from libs.users.inputs import FindOrCreateUserFromAuthProviderInput
from libs.users.services import UserService
from scripts.dev_guard import refuse_outside_local_development

ADMIN_EMAIL = "dev-admin@example.com"
CREATOR_EMAIL = "dev-creator@example.com"
LOW_BALANCE_EMAIL = "dev-low@example.com"
BROKE_EMAIL = "dev-broke@example.com"
READER_EMAIL = "dev-reader@example.com"
SUSPENDED_EMAIL = "dev-suspended@example.com"
NEWCOMER_EMAIL = "dev-newcomer@example.com"
INVITED_EMAIL = "dev-invited@example.com"
SEED_EMAIL_LIST = (
    ADMIN_EMAIL,
    CREATOR_EMAIL,
    LOW_BALANCE_EMAIL,
    BROKE_EMAIL,
    READER_EMAIL,
    SUSPENDED_EMAIL,
    NEWCOMER_EMAIL,
    INVITED_EMAIL,
)

UNUSED_INVITE_NAME = "Dev seed: unused invite"
USED_INVITE_NAME = "Dev seed: used invite"
EXPIRED_INVITE_NAME = "Dev seed: expired invite"
REVOKED_INVITE_NAME = "Dev seed: revoked invite"

PUBLISHED_POST_COUNT = 50
PUBLISHED_POST_SPACING_HOURS = 28
CHARGE_COUNT = 24
REFUND_COUNT = 4
LEDGER_ROW_SPACING_HOURS = 7

POST_TOPIC_LIST = (
    "Slow Mornings",
    "Bread and Patience",
    "Notes on Walking",
    "A Small Garden",
    "Rainy Day Reading",
    "Cooking for One",
    "Learning to Listen",
    "Old Maps",
    "Quiet Streets",
    "The Long Way Home",
)


class CreateSeedUserResult(BaseModel):
    id: int
    identity: UUID
    is_created: bool


class DevSeedService:
    """Adds the dev cases through the lib services, and through the Orm where none makes the
    write, all on one session."""

    def __init__(
        self,
        db_session: AsyncSession,
        db_session_factory: async_sessionmaker[AsyncSession],
        app_settings: AppSettings,
    ) -> None:
        self._db_session = db_session
        self._now: datetime
        self._added_line_list: list[str] = []
        self._skipped_line_list: list[str] = []
        self._note_line_list: list[str] = []

        pagination_service = PaginationService(db_session=db_session)
        self._user_service = UserService(
            db_session=db_session,
            low_credit_balance_threshold_usd=app_settings.credits.low_balance_threshold_usd,
        )
        self._credit_ledger_service = CreditLedgerService(db_session=db_session)
        self._permission_service = PermissionService(db_session=db_session)
        self._admin_credit_service = AdminCreditService(
            db_session=db_session,
            credit_ledger_service=self._credit_ledger_service,
            user_service=self._user_service,
            pagination_service=pagination_service,
        )
        self._admin_user_service = AdminUserService(
            db_session=db_session, pagination_service=pagination_service
        )
        self._admin_invite_service = AdminInviteService(
            db_session=db_session,
            frontend_url=app_settings.auth.frontend_url,
            pagination_service=pagination_service,
        )
        self._invite_service = InviteService(
            db_session=db_session,
            credit_ledger_service=self._credit_ledger_service,
            user_service=self._user_service,
        )
        self._persona_service = PersonaService(
            db_session=db_session, pagination_service=pagination_service
        )
        self._content_engagement_service = ContentEngagementService(
            db_session=db_session,
            content_engagement_settings=app_settings.content_engagement,
        )
        self._blog_post_service = BlogPostService(
            db_session=db_session,
            content_item_service=ContentItemService(
                db_session=db_session,
                content_engagement_service=self._content_engagement_service,
            ),
            persona_service=self._persona_service,
            generate_text_run_service=GenerateTextRunService(db_session_factory=db_session_factory),
            generate_text_step_service=GenerateTextStepService(
                db_session_factory=db_session_factory, credit_settings=app_settings.credits
            ),
            pagination_service=pagination_service,
        )

    async def seed(self) -> None:
        """Adds every case that isn't there yet and rescores the feed."""
        # The database clock is the "now" every backdated time counts from
        now_query = select(DatabaseClockUtils.build_utc_now_sql())
        self._now = await self._db_session.scalar(now_query)

        admin_auth_user = await self._seed_admin()
        await self._seed_creator(admin_auth_user)
        await self._seed_low_balance_creator(admin_auth_user)
        await self._seed_broke_creator(admin_auth_user)
        await self._seed_reader()
        await self._seed_suspended_creator(admin_auth_user)
        await self._seed_newcomer()
        await self._seed_invites(admin_auth_user)

        # Score the feed now that every post exists
        await self._content_engagement_service.rescore_all_engagement()

    def print_summary(self) -> None:
        """Prints what was added, what was skipped, and the notes worth reading."""
        for line_group_title, line_list in (
            ("Added", self._added_line_list),
            ("Skipped (already there)", self._skipped_line_list),
            ("Notes", self._note_line_list),
        ):
            if line_list:
                print(f"{line_group_title}:")
                for line in line_list:
                    print(f"  {line}")

    async def _seed_admin(self) -> AuthUser:
        create_seed_user_result = await self._create_user(ADMIN_EMAIL, "Dev Admin", 2)
        admin_auth_user = await self._build_auth_user(create_seed_user_result, RoleType.ADMIN)
        if not create_seed_user_result.is_created:
            return admin_auth_user

        # No service makes an admin, so the role is set on the row
        admin_role_id_query = select(RoleOrm.id).where(RoleOrm.code == RoleType.ADMIN)
        admin_role_id = await self._db_session.scalar(admin_role_id_query)
        user_record = await self._db_session.get(UserOrm, create_seed_user_result.id)
        user_record.role_id = admin_role_id
        await self._db_session.flush()

        await self._grant_credits(create_seed_user_result.identity, "20.00", admin_auth_user)
        return admin_auth_user

    async def _seed_creator(self, admin_auth_user: AuthUser) -> None:
        create_seed_user_result = await self._create_user(CREATOR_EMAIL, "Dev Creator", 1)
        if not create_seed_user_result.is_created:
            return

        # Two grants, 24 charges and 4 refunds: 30 rows, ending at a balance of $5.00
        await self._grant_credits(create_seed_user_result.identity, "8.00", admin_auth_user)
        await self._grant_credits(create_seed_user_result.identity, "2.00", admin_auth_user)
        await self._add_ledger_rows(
            create_seed_user_result.id, CreditLedgerEntryType.CHARGE, "0.25", CHARGE_COUNT
        )
        await self._add_ledger_rows(
            create_seed_user_result.id, CreditLedgerEntryType.REFUND, "0.25", REFUND_COUNT
        )

        # Two public personas with a post a day or so apart, one private persona
        creator_auth_user = await self._build_auth_user(create_seed_user_result, RoleType.CREATOR)
        ada_identity = await self._create_persona(
            creator_auth_user,
            "Ada Quill",
            "A home baker who writes plainly about bread and the patience it asks for.",
            is_public=True,
        )
        bram_identity = await self._create_persona(
            creator_auth_user,
            "Bram Holt",
            "A retired surveyor who walks every morning and writes down what he notices.",
            is_public=True,
        )
        cass_identity = await self._create_persona(
            creator_auth_user,
            "Cass Mire",
            "A private persona for drafts that are not ready for anyone yet.",
            is_public=False,
        )

        # About 50 published public posts over the last 60 days, alternating personas
        for post_number in range(1, PUBLISHED_POST_COUNT + 1):
            persona_identity = ada_identity if post_number % 2 else bram_identity
            published_at = self._now - timedelta(
                hours=PUBLISHED_POST_SPACING_HOURS * (post_number - 1) + 6
            )
            await self._create_post(
                creator_auth_user, persona_identity, post_number, True, published_at
            )

        # A scheduled post, three drafts, and a public post under the private persona
        scheduled_published_at = self._now + timedelta(days=3)
        await self._create_post(creator_auth_user, bram_identity, 101, True, scheduled_published_at)
        for draft_number in (201, 202, 203):
            await self._create_post(creator_auth_user, ada_identity, draft_number, False, None)
        await self._create_post(
            creator_auth_user, cass_identity, 301, True, self._now - timedelta(days=2)
        )

    async def _seed_low_balance_creator(self, admin_auth_user: AuthUser) -> None:
        create_seed_user_result = await self._create_user(LOW_BALANCE_EMAIL, "Dev Low", 1)
        if not create_seed_user_result.is_created:
            return

        # $1.00 granted and $0.58 spent leaves $0.42, below the low balance threshold
        await self._grant_credits(create_seed_user_result.identity, "1.00", admin_auth_user)
        await self._add_ledger_rows(
            create_seed_user_result.id, CreditLedgerEntryType.CHARGE, "0.29", 2
        )
        creator_auth_user = await self._build_auth_user(create_seed_user_result, RoleType.CREATOR)
        persona_identity = await self._create_persona(
            creator_auth_user,
            "Lena Frost",
            "Writes short notes on getting by on very little.",
            is_public=True,
        )
        await self._create_post(
            creator_auth_user, persona_identity, 401, True, self._now - timedelta(days=5)
        )

    async def _seed_broke_creator(self, admin_auth_user: AuthUser) -> None:
        create_seed_user_result = await self._create_user(BROKE_EMAIL, "Dev Broke", 1)
        if not create_seed_user_result.is_created:
            return

        # A creator who has spent everything: $1.00 granted and $1.00 charged
        set_user_role_input = AdminSetUserRoleInput(role=RoleType.CREATOR)
        await self._admin_user_service.set_user_role(
            create_seed_user_result.identity, set_user_role_input, admin_auth_user
        )
        await self._grant_credits(create_seed_user_result.identity, "1.00", admin_auth_user)
        await self._add_ledger_rows(
            create_seed_user_result.id, CreditLedgerEntryType.CHARGE, "1.00", 1
        )

    async def _seed_reader(self) -> None:
        await self._create_user(READER_EMAIL, "Dev Reader", 1)

    async def _seed_suspended_creator(self, admin_auth_user: AuthUser) -> None:
        create_seed_user_result = await self._create_user(SUSPENDED_EMAIL, "Dev Suspended", 20)
        if not create_seed_user_result.is_created:
            return

        # A creator with a public persona and a few public posts, who is then suspended
        await self._grant_credits(create_seed_user_result.identity, "3.00", admin_auth_user)
        creator_auth_user = await self._build_auth_user(create_seed_user_result, RoleType.CREATOR)
        persona_identity = await self._create_persona(
            creator_auth_user,
            "Dara Voss",
            "A travel writer whose posts are hidden while her account is suspended.",
            is_public=True,
        )
        for post_number in (501, 502, 503):
            published_at = self._now - timedelta(days=post_number - 500)
            await self._create_post(
                creator_auth_user, persona_identity, post_number, True, published_at
            )
        set_user_active_input = AdminSetUserActiveInput(is_active=False)
        await self._admin_user_service.set_user_active(
            create_seed_user_result.identity, set_user_active_input, admin_auth_user
        )

    async def _seed_newcomer(self) -> None:
        # Signed up and never came back: no name and no last activity
        await self._create_user(NEWCOMER_EMAIL, None, None)

    async def _seed_invites(self, admin_auth_user: AuthUser) -> None:
        # Unused: the link is the only time the code can be seen
        is_unused_invite_new = await self._is_invite_new(UNUSED_INVITE_NAME)
        is_used_invite_new = await self._is_invite_new(USED_INVITE_NAME)
        is_expired_invite_new = await self._is_invite_new(EXPIRED_INVITE_NAME)
        is_revoked_invite_new = await self._is_invite_new(REVOKED_INVITE_NAME)
        if is_unused_invite_new:
            admin_create_invite_result = await self._create_invite(
                UNUSED_INVITE_NAME, 30, admin_auth_user
            )
            self._note_line_list.append(
                f"Unused invite link (shown only now): {admin_create_invite_result.invite_url}"
            )

        # Used: redeemed by dev-invited, who becomes a creator with the invite's credits
        if is_used_invite_new:
            admin_create_invite_result = await self._create_invite(
                USED_INVITE_NAME, 30, admin_auth_user
            )
            invite_code = admin_create_invite_result.invite_url.rsplit("/", maxsplit=1)[1]
            create_seed_user_result = await self._create_user(INVITED_EMAIL, "Dev Invited", 1)
            redeem_invite_result = await self._invite_service.redeem_invite(
                invite_code, create_seed_user_result.id
            )
            if redeem_invite_result.result_type != InviteSignInResultType.ACCEPTED:
                raise SystemExit(f"Redeeming the seed invite failed: {redeem_invite_result}")

        # Expired: made, then its expiry moved into the past
        if is_expired_invite_new:
            admin_create_invite_result = await self._create_invite(
                EXPIRED_INVITE_NAME, 1, admin_auth_user
            )
            invite_query = select(InviteOrm).where(
                InviteOrm.identity == admin_create_invite_result.identity
            )
            invite_record = await self._db_session.scalar(invite_query)
            invite_record.created_at = self._now - timedelta(days=10)
            invite_record.expires_at = self._now - timedelta(days=3)
            await self._db_session.flush()

        # Revoked
        if is_revoked_invite_new:
            admin_create_invite_result = await self._create_invite(
                REVOKED_INVITE_NAME, 30, admin_auth_user
            )
            await self._admin_invite_service.revoke_invite(
                admin_create_invite_result.identity, admin_auth_user
            )

    async def _create_user(
        self, email: str, display_name: str | None, last_activity_days_ago: int | None
    ) -> CreateSeedUserResult:
        """Signs the user up as a Google sign-in would, as a reader; an existing email is
        returned with is_created False."""
        user_query = select(UserOrm.id, UserOrm.identity).where(UserOrm.email == email)
        user_query_result = await self._db_session.execute(user_query)
        user_row = user_query_result.one_or_none()
        if user_row is not None:
            self._skipped_line_list.append(f"user {email}")
            return CreateSeedUserResult(
                id=user_row.id, identity=user_row.identity, is_created=False
            )

        find_or_create_input = FindOrCreateUserFromAuthProviderInput(
            provider=AuthProviderType.GOOGLE,
            provider_subject=f"dev-seed-{email}",
            email=email,
            is_email_verified=True,
            display_name=display_name,
            avatar_url=None,
        )
        find_or_create_result = await self._user_service.find_or_create_user_from_auth_provider(
            find_or_create_input
        )

        # Sign-in records no activity, so a user who came back gets backdated times
        if last_activity_days_ago is not None:
            user_record = await self._db_session.get(UserOrm, find_or_create_result.id)
            user_record.last_login_at = self._now - timedelta(days=last_activity_days_ago)
            user_record.last_activity_at = self._now - timedelta(days=last_activity_days_ago)
            await self._db_session.flush()

        self._added_line_list.append(f"user {email}")
        return CreateSeedUserResult(
            id=find_or_create_result.id, identity=find_or_create_result.identity, is_created=True
        )

    async def _build_auth_user(
        self, create_seed_user_result: CreateSeedUserResult, role: RoleType
    ) -> AuthUser:
        find_role_permission_list_result = await self._permission_service.find_role_permission_list(
            role
        )
        return AuthUser(
            id=create_seed_user_result.id,
            identity=create_seed_user_result.identity,
            role=role,
            permissions=frozenset(find_role_permission_list_result.permissions),
        )

    async def _grant_credits(
        self, user_identity: UUID, amount_usd: str, admin_auth_user: AuthUser
    ) -> None:
        grant_user_credits_input = AdminGrantUserCreditsInput(
            amount_usd=Decimal(amount_usd), note="Dev seed grant"
        )
        await self._admin_credit_service.grant_user_credits(
            user_identity, grant_user_credits_input, admin_auth_user
        )

    async def _add_ledger_rows(
        self, user_id: int, entry_type: CreditLedgerEntryType, amount_usd: str, row_count: int
    ) -> None:
        """Adds charge or refund rows tied to no run, spread over the past days, and moves
        the balance by their total; no service writes these."""
        # A charge takes from the balance and a refund gives back
        sign = -1 if entry_type == CreditLedgerEntryType.CHARGE else 1
        signed_amount_usd = sign * Decimal(amount_usd)
        for row_number in range(1, row_count + 1):
            row_age = timedelta(hours=LEDGER_ROW_SPACING_HOURS * row_number)
            credit_ledger_record = CreditLedgerOrm(
                user_id=user_id,
                amount_usd=signed_amount_usd,
                entry_type=entry_type,
                note=f"Dev seed {entry_type.lower()}",
                created_at=self._now - row_age,
                created_by_id=user_id,
                updated_by_id=user_id,
            )
            self._db_session.add(credit_ledger_record)
        await self._db_session.flush()

        # A SQL expression, as the ledger service writes it
        credit_balance_update = (
            update(UserOrm)
            .where(UserOrm.id == user_id)
            .values(credit_balance_usd=UserOrm.credit_balance_usd + signed_amount_usd * row_count)
        )
        await self._db_session.execute(credit_balance_update)

    async def _create_persona(
        self, creator_auth_user: AuthUser, name: str, bio: str, is_public: bool
    ) -> UUID:
        persona_input = PersonaInput(
            name=name,
            bio=bio,
            avatar_url=None,
            background=f"{name} has written for years and keeps a notebook for everything.",
            writing_style="Plain, warm and concrete, with short paragraphs.",
            default_tone="Reflective",
            default_target_audience="Curious general readers",
            sample_writing=f"{name} starts most mornings the same way: slowly, and with tea.",
            is_public=is_public,
        )
        create_persona_result = await self._persona_service.create_persona(
            persona_input, creator_auth_user
        )
        self._added_line_list.append(f"persona {name}")
        return create_persona_result.identity

    async def _create_post(
        self,
        creator_auth_user: AuthUser,
        persona_identity: UUID,
        post_number: int,
        is_public: bool,
        published_at: datetime | None,
    ) -> None:
        topic = POST_TOPIC_LIST[post_number % len(POST_TOPIC_LIST)]
        create_blog_post_input = CreateBlogPostInput(
            persona_identity=persona_identity,
            title=f"{topic}, Entry {post_number}",
            subtitle=f"A short note on {topic.lower()}" if post_number % 3 else None,
            body=self._build_post_body(topic, post_number),
            is_public=is_public,
            published_at=published_at,
        )
        await self._blog_post_service.create_blog_post(create_blog_post_input, creator_auth_user)

    def _build_post_body(self, topic: str, post_number: int) -> str:
        return (
            f"## Where it starts\n\n"
            f"This is entry {post_number}, and it is about {topic.lower()}. "
            f"It is a short post written for the dev database.\n\n"
            f"## What I noticed\n\n"
            f"Most days the small things matter more than the big ones.\n\n"
            f"### A closer look\n\n"
            f"Entry {post_number} ends here, with a plain sentence about {topic.lower()}.\n"
        )

    async def _is_invite_new(self, invite_name: str) -> bool:
        invite_query = select(InviteOrm.id).where(InviteOrm.name == invite_name)
        invite_id = await self._db_session.scalar(invite_query)
        if invite_id is None:
            self._added_line_list.append(f"invite {invite_name}")
            return True
        self._skipped_line_list.append(f"invite {invite_name}")
        if invite_name == UNUSED_INVITE_NAME:
            self._note_line_list.append("The unused invite's link can't be shown again.")
        return False

    async def _create_invite(
        self, name: str, expires_in_days: int, admin_auth_user: AuthUser
    ) -> AdminCreateInviteResult:
        admin_create_invite_input = AdminCreateInviteInput(
            name=name,
            credit_amount_usd=Decimal("3.00"),
            note="Dev seed invite",
            expires_in_days=expires_in_days,
        )
        return await self._admin_invite_service.create_invite(
            admin_create_invite_input, admin_auth_user
        )


async def _seed_database() -> None:
    app_settings = AppSettings()
    refuse_outside_local_development(app_settings)

    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    try:
        async with db_session_factory() as db_session, db_session.begin():
            dev_seed_service = DevSeedService(db_session, db_session_factory, app_settings)
            await dev_seed_service.seed()
    finally:
        await db_engine.dispose()
    dev_seed_service.print_summary()


def main() -> int:
    """Seeds the local development database and prints what it added and skipped."""
    asyncio.run(_seed_database())
    return 0


if __name__ == "__main__":
    sys.exit(main())
