from libs.google_auth.results import GoogleIdentityResult


def build_google_identity_result(
    *,
    provider_subject: str = "google-subject-stub",
    email: str = "ada@example.com",
    is_email_verified: bool = True,
    display_name: str | None = "Ada Lovelace",
    avatar_url: str | None = "https://example.com/ada.png",
    invite_code: str | None = None,
) -> GoogleIdentityResult:
    return GoogleIdentityResult(
        provider_subject=provider_subject,
        email=email,
        is_email_verified=is_email_verified,
        display_name=display_name,
        avatar_url=avatar_url,
        invite_code=invite_code,
    )
