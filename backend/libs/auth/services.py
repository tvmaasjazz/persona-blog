import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from google.auth import jwt
from httpx import AsyncClient, HTTPError
from redis.asyncio import Redis

from libs.auth.constants import (
    GOOGLE_AUTHORIZATION_URL,
    GOOGLE_ISSUERS,
    GOOGLE_SCOPES,
    GOOGLE_TOKEN_URL,
    OAUTH_STATE_KEY_PREFIX,
    SESSION_KEY_PREFIX,
)
from libs.auth.results import AuthUser, GoogleIdentityResult, GoogleSignInResult
from libs.auth.settings import AuthSettings
from libs.auth.types import AuthProviderType
from libs.core.exceptions import ServiceUnavailableException, UnauthorizedException
from libs.users.inputs import FindOrCreateUserFromAuthProviderInput
from libs.users.services import UserService


class GoogleOAuthService:
    def __init__(
        self,
        http_client: AsyncClient,
        redis_client: Redis,
        auth_settings: AuthSettings,
        google_client_id: str,
        google_client_secret: str,
    ) -> None:
        self._http_client = http_client
        self._redis_client = redis_client
        self._auth_settings = auth_settings
        self._google_client_id = google_client_id
        self._google_client_secret = google_client_secret

    async def build_authorization_url(self) -> str:
        oauth_state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        stored_state = json.dumps({"nonce": nonce, "code_verifier": code_verifier})
        await self._redis_client.set(
            f"{OAUTH_STATE_KEY_PREFIX}{oauth_state}",
            stored_state,
            ex=self._auth_settings.oauth_state_ttl_seconds,
        )

        authorization_query = urlencode(
            {
                "client_id": self._google_client_id,
                "redirect_uri": self._auth_settings.google_redirect_url,
                "response_type": "code",
                "scope": " ".join(GOOGLE_SCOPES),
                "state": oauth_state,
                "nonce": nonce,
                "code_challenge": _build_code_challenge(code_verifier),
                "code_challenge_method": "S256",
                "access_type": "online",
                "prompt": "select_account",
            }
        )
        return f"{GOOGLE_AUTHORIZATION_URL}?{authorization_query}"

    async def exchange_code_for_identity(self, code: str, oauth_state: str) -> GoogleIdentityResult:
        stored_state = await self._redis_client.getdel(f"{OAUTH_STATE_KEY_PREFIX}{oauth_state}")
        if stored_state is None:
            raise UnauthorizedException("Sign-in state is missing or expired")

        code_verifier = json.loads(stored_state)["code_verifier"]
        nonce = json.loads(stored_state)["nonce"]
        id_token = await self._exchange_code_for_id_token(code, code_verifier)
        id_token_claims = jwt.decode(id_token, verify=False)
        _validate_id_token_claims(id_token_claims, self._google_client_id, nonce)

        return GoogleIdentityResult(
            provider_subject=id_token_claims["sub"],
            email=id_token_claims["email"],
            is_email_verified=id_token_claims.get("email_verified", False),
            display_name=id_token_claims.get("name"),
            avatar_url=id_token_claims.get("picture"),
        )

    async def _exchange_code_for_id_token(self, code: str, code_verifier: str) -> str:
        try:
            token_response = await self._http_client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self._google_client_id,
                    "client_secret": self._google_client_secret,
                    "redirect_uri": self._auth_settings.google_redirect_url,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
                timeout=self._auth_settings.google_request_timeout_seconds,
            )
        except HTTPError as http_error:
            raise ServiceUnavailableException("Google sign-in is unavailable") from http_error

        if token_response.status_code != 200:
            raise UnauthorizedException("Google rejected the sign-in code")

        id_token = token_response.json().get("id_token")
        if id_token is None:
            raise ServiceUnavailableException("Google returned no id token")
        return id_token


class AuthSessionService:
    def __init__(self, redis_client: Redis, auth_settings: AuthSettings) -> None:
        self._redis_client = redis_client
        self._auth_settings = auth_settings

    async def create_session(self, user_id: int, user_identity: UUID) -> str:
        session_id = secrets.token_urlsafe(32)
        auth_user = AuthUser(id=user_id, identity=user_identity)
        await self._redis_client.set(
            f"{SESSION_KEY_PREFIX}{session_id}",
            auth_user.model_dump_json(),
            ex=self._auth_settings.session_ttl_seconds,
        )
        return session_id

    async def find_session(self, session_id: str) -> AuthUser:
        stored_session = await self._redis_client.get(f"{SESSION_KEY_PREFIX}{session_id}")
        if stored_session is None:
            raise UnauthorizedException("Session is missing or expired")
        return AuthUser.model_validate_json(stored_session)

    async def delete_session(self, session_id: str) -> None:
        await self._redis_client.delete(f"{SESSION_KEY_PREFIX}{session_id}")


class GoogleSignInService:
    """The sign-in flow: Google identity, then the user row, then the session."""

    def __init__(
        self,
        google_oauth_service: GoogleOAuthService,
        user_service: UserService,
        auth_session_service: AuthSessionService,
    ) -> None:
        self._google_oauth_service = google_oauth_service
        self._user_service = user_service
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
        session_id = await self._auth_session_service.create_session(
            user_id=find_or_create_user_from_auth_provider_result.id,
            user_identity=find_or_create_user_from_auth_provider_result.identity,
        )
        return GoogleSignInResult(
            session_id=session_id,
            is_new_user=find_or_create_user_from_auth_provider_result.is_new_user,
        )


def _build_code_challenge(code_verifier: str) -> str:
    code_verifier_digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(code_verifier_digest).rstrip(b"=").decode()


def _validate_id_token_claims(
    id_token_claims: dict[str, Any], google_client_id: str, nonce: str
) -> None:
    # The id token came straight from Google's token endpoint over TLS, so the channel
    # already proves who issued it. These checks prove it was issued for this client and
    # for this sign-in attempt.
    if id_token_claims.get("aud") != google_client_id:
        raise UnauthorizedException("Google id token was issued for another client")
    if id_token_claims.get("iss") not in GOOGLE_ISSUERS:
        raise UnauthorizedException("Google id token has an unexpected issuer")
    if id_token_claims.get("nonce") != nonce:
        raise UnauthorizedException("Google id token does not match this sign-in")

    expires_at = id_token_claims.get("exp")
    if expires_at is None or datetime.fromtimestamp(expires_at, UTC) <= datetime.now(UTC):
        raise UnauthorizedException("Google id token has expired")
