from libs.auth.services import AuthSessionService
from libs.auth.types import AuthProviderType
from libs.google_auth.results import GoogleSignInResult
from libs.google_auth.services.google_oauth_service import GoogleOAuthService
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
    ) -> None:
        self._google_oauth_service = google_oauth_service
        self._user_service = user_service
        self._user_activity_service = user_activity_service
        self._auth_session_service = auth_session_service

    async def sign_in_with_google(self, code: str, oauth_state: str) -> GoogleSignInResult:
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
        session_id = await self._auth_session_service.create_session(
            user_id=find_or_create_user_from_auth_provider_result.id,
            user_identity=find_or_create_user_from_auth_provider_result.identity,
        )
        return GoogleSignInResult(
            session_id=session_id,
            is_new_user=find_or_create_user_from_auth_provider_result.is_new_user,
        )
