from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.auth.types import AuthProviderType
from libs.google_auth.results import GoogleSignInResult
from libs.google_auth.services.google_oauth_service import GoogleOAuthService
from libs.invites.services import InviteService
from libs.permissions.services import PermissionService
from libs.permissions.types import RoleType
from libs.users.inputs import FindOrCreateUserFromAuthProviderInput
from libs.users.services import UserActivityService, UserService


class GoogleSignInService:
    """The sign-in flow: Google identity, then the user row, then the session."""

    def __init__(
        self,
        google_oauth_service: GoogleOAuthService,
        user_service: UserService,
        user_activity_service: UserActivityService,
        auth_session_service: AuthSessionService,
        permission_service: PermissionService,
        invite_service: InviteService,
    ) -> None:
        self._google_oauth_service = google_oauth_service
        self._user_service = user_service
        self._user_activity_service = user_activity_service
        self._auth_session_service = auth_session_service
        self._permission_service = permission_service
        self._invite_service = invite_service

    async def sign_in_with_google(self, code: str, oauth_state: str) -> GoogleSignInResult:
        """Creates the user's account on first sign-in, redeems the invite the sign-in carries,
        and returns a new session id and the invite's outcome."""
        google_identity_result = await self._google_oauth_service.exchange_code_for_identity(
            code, oauth_state
        )
        find_or_create_user_from_auth_provider_input = FindOrCreateUserFromAuthProviderInput(
            provider=AuthProviderType.GOOGLE,
            provider_subject=google_identity_result.provider_subject,
            email=google_identity_result.email,
            is_email_verified=google_identity_result.is_email_verified,
            display_name=google_identity_result.display_name,
            avatar_url=google_identity_result.avatar_url,
        )
        find_or_create_user_from_auth_provider_result = (
            await self._user_service.find_or_create_user_from_auth_provider(
                find_or_create_user_from_auth_provider_input
            )
        )
        await self._user_activity_service.record_sign_in(
            user_id=find_or_create_user_from_auth_provider_result.id,
            user_auth_provider_id=(
                find_or_create_user_from_auth_provider_result.user_auth_provider_id
            ),
        )

        # Redeem the invite, if the sign-in carried one; a refusal doesn't fail the sign-in
        user_role = find_or_create_user_from_auth_provider_result.role
        invite_sign_in_result_type = None
        if google_identity_result.invite_code is not None:
            redeem_invite_result = await self._invite_service.redeem_invite(
                google_identity_result.invite_code,
                find_or_create_user_from_auth_provider_result.id,
            )
            invite_sign_in_result_type = redeem_invite_result.result_type
            # The session carries the role the redemption left
            if redeem_invite_result.is_made_creator:
                user_role = RoleType.CREATOR

        find_role_permission_list_result = await self._permission_service.find_role_permission_list(
            user_role
        )
        auth_user = AuthUser(
            id=find_or_create_user_from_auth_provider_result.id,
            identity=find_or_create_user_from_auth_provider_result.identity,
            role=user_role,
            permissions=frozenset(find_role_permission_list_result.permissions),
        )
        session_id = await self._auth_session_service.create_session(auth_user)
        return GoogleSignInResult(
            session_id=session_id,
            is_new_user=find_or_create_user_from_auth_provider_result.is_new_user,
            invite_sign_in_result_type=invite_sign_in_result_type,
        )
