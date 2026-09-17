from libs.auth.results import GoogleIdentityResult
from libs.auth.services import GoogleOAuthService


class GoogleOAuthServiceStub(GoogleOAuthService):
    def __init__(self) -> None:
        self.build_authorization_url_result = "https://accounts.google.com/o/oauth2/v2/auth?stub=1"
        self.exchange_code_for_identity_result = GoogleIdentityResult(
            provider_subject="google-subject-stub",
            email="ada@example.com",
            is_email_verified=True,
            display_name="Ada Lovelace",
            avatar_url="https://example.com/ada.png",
        )
        self.exchange_code_for_identity_error: Exception | None = None

    async def build_authorization_url(self) -> str:
        return self.build_authorization_url_result

    async def exchange_code_for_identity(self, code: str, oauth_state: str) -> GoogleIdentityResult:
        if self.exchange_code_for_identity_error is not None:
            raise self.exchange_code_for_identity_error
        return self.exchange_code_for_identity_result
