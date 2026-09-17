import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any


def build_google_id_token(
    *,
    aud: str = "test-google-client-id",
    iss: str = "https://accounts.google.com",
    sub: str = "google-subject-1",
    email: str = "ada@example.com",
    email_verified: bool = True,
    name: str | None = "Ada Lovelace",
    picture: str | None = "https://example.com/ada.png",
    nonce: str = "test-nonce",
    exp: int | None = None,
) -> str:
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "aud": aud,
        "iss": iss,
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": picture,
        "nonce": nonce,
        "exp": exp if exp is not None else _build_default_exp(),
    }
    header_segment = _encode_segment(header)
    claims_segment = _encode_segment(claims)
    signature_segment = _encode_segment({"unsigned": True})
    return f"{header_segment}.{claims_segment}.{signature_segment}"


def build_google_token_response_body(*, id_token: str | None = None) -> dict[str, str]:
    return {"id_token": id_token if id_token is not None else build_google_id_token()}


def _encode_segment(segment: dict[str, Any]) -> str:
    segment_json = json.dumps(segment).encode()
    return base64.urlsafe_b64encode(segment_json).rstrip(b"=").decode()


def _build_default_exp() -> int:
    default_expires_at = datetime.now(UTC) + timedelta(hours=1)
    return int(default_expires_at.timestamp())
