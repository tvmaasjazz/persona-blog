import base64
import hashlib
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from google.auth import jwt
from httpx import AsyncClient, HTTPError

from libs.auth.results import OAuthStateResult
from libs.auth.services import OAuthStateService
from libs.core.exceptions import ServiceUnavailableException, UnauthorizedException
from libs.google_auth.constants import (
    GOOGLE_AUTHORIZATION_URL,
    GOOGLE_ISSUERS,
    GOOGLE_SCOPES,
    GOOGLE_TOKEN_URL,
)
from libs.google_auth.results import GoogleIdentityResult
from libs.google_auth.settings import GoogleAuthSettings


class GoogleOAuthService:
    def __init__(
        self,
        http_client: AsyncClient,
        oauth_state_service: OAuthStateService,
        google_auth_settings: GoogleAuthSettings,
        google_client_id: str,
        google_client_secret: str,
    ) -> None:
        self._http_client = http_client
        self._oauth_state_service = oauth_state_service
        self._google_auth_settings = google_auth_settings
        self._google_client_id = google_client_id
        self._google_client_secret = google_client_secret

    async def build_authorization_url(self) -> str:
        oauth_state_result = await self._oauth_state_service.create_state()
        authorization_query = urlencode(
            {
                "client_id": self._google_client_id,
                "redirect_uri": self._google_auth_settings.redirect_url,
                "response_type": "code",
                "scope": " ".join(GOOGLE_SCOPES),
                "state": oauth_state_result.oauth_state,
                "nonce": oauth_state_result.nonce,
                "code_challenge": _build_code_challenge(oauth_state_result.code_verifier),
                "code_challenge_method": "S256",
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return f"{GOOGLE_AUTHORIZATION_URL}?{authorization_query}"

    async def exchange_code_for_identity(self, code: str, oauth_state: str) -> GoogleIdentityResult:
        oauth_state_result = await self._oauth_state_service.consume_state(oauth_state)
        id_token = await self._exchange_code_for_id_token(code, oauth_state_result)
        id_token_claims = jwt.decode(id_token, verify=False)
        self._validate_id_token_claims(id_token_claims, oauth_state_result.nonce)

        return GoogleIdentityResult(
            provider_subject=id_token_claims["sub"],
            email=id_token_claims["email"],
            is_email_verified=id_token_claims.get("email_verified", False),
            display_name=id_token_claims.get("name"),
            avatar_url=id_token_claims.get("picture"),
        )

    async def _exchange_code_for_id_token(
        self, code: str, oauth_state_result: OAuthStateResult
    ) -> str:
        try:
            token_response = await self._http_client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self._google_client_id,
                    "client_secret": self._google_client_secret,
                    "redirect_uri": self._google_auth_settings.redirect_url,
                    "grant_type": "authorization_code",
                    "code_verifier": oauth_state_result.code_verifier,
                },
                timeout=self._google_auth_settings.request_timeout_seconds,
            )
        except HTTPError as http_error:
            raise ServiceUnavailableException("Google sign-in is unavailable") from http_error

        if token_response.status_code != 200:
            raise UnauthorizedException("Google rejected the sign-in code")

        id_token = token_response.json().get("id_token")
        if id_token is None:
            raise ServiceUnavailableException("Google returned no id token")
        return id_token

    def _validate_id_token_claims(self, id_token_claims: dict[str, Any], nonce: str) -> None:
        # TLS already proves Google issued the token; check it was for this client and attempt
        if id_token_claims.get("aud") != self._google_client_id:
            raise UnauthorizedException("Google id token was issued for another client")
        if id_token_claims.get("iss") not in GOOGLE_ISSUERS:
            raise UnauthorizedException("Google id token has an unexpected issuer")
        if id_token_claims.get("nonce") != nonce:
            raise UnauthorizedException("Google id token does not match this sign-in")

        expires_at = id_token_claims.get("exp")
        if expires_at is None or datetime.fromtimestamp(expires_at, UTC) <= datetime.now(UTC):
            raise UnauthorizedException("Google id token has expired")


def _build_code_challenge(code_verifier: str) -> str:
    code_verifier_digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(code_verifier_digest).rstrip(b"=").decode()
