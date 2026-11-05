from libs.auth.services import OAuthStateService
from libs.google_auth.results import GoogleIdentityResult
from libs.google_auth.services import GoogleOAuthService


class GoogleOAuthServiceStub(GoogleOAuthService):
    def __init__(self) -> None:
        self.build_authorization_url_inputs: list[str | None] = []
        self.build_authorization_url_result = "https://accounts.google.com/o/oauth2/v2/auth?stub=1"
        # When set, the invite code is stored in a real OAuth state, as the real service does
        self.build_authorization_url_oauth_state_service: OAuthStateService | None = None
        self.exchange_code_for_identity_result = GoogleIdentityResult(
            provider_subject="google-subject-stub",
            email="ada@example.com",
            is_email_verified=True,
            display_name="Ada Lovelace",
            avatar_url="https://example.com/ada.png",
            invite_code=None,
        )
        self.exchange_code_for_identity_error: Exception | None = None

    async def build_authorization_url(self, invite_code: str | None = None) -> str:
        self.build_authorization_url_inputs.append(invite_code)
        if self.build_authorization_url_oauth_state_service is not None:
            await self.build_authorization_url_oauth_state_service.create_state(invite_code)
        return self.build_authorization_url_result

    async def exchange_code_for_identity(self, code: str, oauth_state: str) -> GoogleIdentityResult:
        if self.exchange_code_for_identity_error is not None:
            raise self.exchange_code_for_identity_error
        return self.exchange_code_for_identity_result
