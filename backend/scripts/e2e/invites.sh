#!/usr/bin/env bash
# Walks invite links end to end against a running dev server: the admin creates invites,
# a code is checked as the invite page would, the Google login refuses codes that can't
# be used before leaving for Google, and revoking works. Prints each response and checks
# what it can. Run from backend/:
#
#   ./scripts/e2e/invites.sh
#
# Using an invite needs a real Google sign-in, so the last step creates a fresh invite
# and prints its link to open in a browser.
#
# It signs in by minting a session for the first admin, so no browser is needed for the
# rest. Make your user the admin first:
#
#   UPDATE pb_user SET role_id = (SELECT id FROM pb_role WHERE code = 'ADMIN')
#   WHERE email = '<your email>';
#
# It refuses to run unless .env points at a local development database.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
RUN_LABEL="e2e invites $(date +%Y%m%d%H%M%S)"
export RUN_LABEL

# Progress goes to stderr, so a response body captured with $( ) stays clean JSON.
step() { printf '\n\033[1m── %s\033[0m\n' "$1" >&2; }
fail() { printf '\033[31mFAIL\033[0m %s\n' "$1" >&2; exit 1; }
pass() { printf '\033[32m  ok\033[0m %s\n' "$1" >&2; }

# Prints the code at the end of an invite link.
read_code_from_url() { python3 -c 'import sys; print(sys.stdin.read().strip().rsplit("/invite/", 1)[1])'; }
# Prints the status of the named invite in a {"invites": [...]} body.
find_invite_status() {
  python3 -c '
import json, sys

invites = json.load(sys.stdin)["invites"]
print(next(invite["status"] for invite in invites if invite["name"] == sys.argv[1]))
' "$1"
}
# Sends a GET without following redirects and prints the status and Location.
request_redirect() {
  curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$1"
}

read_json_field() { python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
# Builds a JSON object from key=value pairs: @NAME reads environment variable NAME as
# a string, anything else is parsed as a JSON literal. See generate_text.sh for
# why the python is single-quoted and the pairs arrive as argv.
json_body() {
  python3 -c '
import json, os, sys

body = {}
for pair in sys.argv[1:]:
    key, _, source = pair.partition("=")
    body[key] = os.environ[source[1:]] if source.startswith("@") else json.loads(source)
print(json.dumps(body))
' "$@"
}
print_json() { python3 -m json.tool; }

# Sends a request, shows the body, and prints it for capture; fails unless the status
# matches. Always capture it into a variable first: inside a pipeline, fail only exits
# the pipeline's subshell.
request() {
  local expected="$1" description="$2" response status body
  shift 2
  response="$(curl -s -w '\n%{http_code}' -b "sid=$SESSION_ID" "$@")"
  status="${response##*$'\n'}"
  body="${response%$'\n'*}"
  # A 500 body is plain text, not JSON, so fall back to printing it as is.
  if [ -n "$body" ]; then echo "$body" | print_json >&2 2>/dev/null || echo "$body" >&2; fi
  [ "$status" = "$expected" ] || fail "$description: expected $expected, got $status"
  pass "$description → $expected"
  echo "$body"
}

step "Checking this is a local development setup"
case "$API_URL" in
  http://localhost:* | http://127.0.0.1:*) ;;
  *) fail "API_URL is $API_URL — these scripts only run against a local dev server" ;;
esac
# The session minting below writes to whatever database .env points at, so refuse
# anything that isn't a local development database.
if ! uv run python - <<'PY'
from urllib.parse import urlparse

from apps.api.core.config import AppSettings
from apps.api.core.types import EnvironmentType

app_settings = AppSettings()
database_host = urlparse(app_settings.database_url).hostname
if app_settings.environment is not EnvironmentType.DEVELOPMENT:
    raise SystemExit(f"environment is {app_settings.environment}, not DEVELOPMENT")
if database_host not in ("localhost", "127.0.0.1"):
    raise SystemExit(f"database host is {database_host}, not localhost")
PY
then
  fail "refusing to run outside local development — check environment and DATABASE_URL"
fi
pass "local development environment and database"

step "Checking the dev server"
if ! curl -sf --max-time 3 "$API_URL/health" >/dev/null; then
  fail "no server at $API_URL — start it with: uv run granian --interface asgi apps.api.main:app --reload"
fi
pass "$API_URL is up"

step "Checking migrations"
if ! uv run alembic current 2>/dev/null | grep -q '(head)'; then
  fail "the database isn't at the latest migration — run: uv run alembic upgrade head"
fi
pass "database is at head"

step "Minting an admin session"
SESSION_ID="$(uv run python - <<'PY'
import asyncio

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.database.orm import RoleOrm, UserOrm
from libs.database.session import create_db_session_factory
from libs.permissions.services import PermissionService
from libs.permissions.types import RoleType


async def main() -> None:
    app_settings = AppSettings()
    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    redis_client = Redis.from_url(app_settings.redis_url)
    try:
        async with db_session_factory() as db_session:
            admin_query = (
                select(UserOrm)
                .join(RoleOrm, RoleOrm.id == UserOrm.role_id)
                .where(RoleOrm.code == RoleType.ADMIN)
                .order_by(UserOrm.id)
            )
            admin_record = await db_session.scalar(admin_query)
            if admin_record is None:
                raise SystemExit(
                    "no admin yet — run: UPDATE pb_user SET role_id = (SELECT id FROM pb_role "
                    "WHERE code = 'ADMIN') WHERE email = '<your email>';"
                )
            permission_service = PermissionService(db_session=db_session)
            find_role_permission_list_result = await permission_service.find_role_permission_list(
                RoleType.ADMIN
            )
        admin_auth_user = AuthUser(
            id=admin_record.id,
            identity=admin_record.identity,
            role=RoleType.ADMIN,
            permissions=frozenset(find_role_permission_list_result.permissions),
        )
        auth_session_service = AuthSessionService(
            redis_client=redis_client, auth_settings=app_settings.auth
        )
        admin_session_id = await auth_session_service.create_session(admin_auth_user)
        print(admin_session_id)
    finally:
        await redis_client.aclose()
        await db_engine.dispose()


asyncio.run(main())
PY
)"
pass "admin session ready"

step "1. Invites that are refused"
request 422 "an amount of 0" -X POST "$API_URL/admin/invites" -H 'Content-Type: application/json' \
  -d "$(json_body name=@RUN_LABEL credit_amount_usd=0)" >/dev/null
request 422 "an amount above \$100" -X POST "$API_URL/admin/invites" -H 'Content-Type: application/json' \
  -d "$(json_body name=@RUN_LABEL credit_amount_usd=100.01)" >/dev/null
request 422 "expiring in 31 days" -X POST "$API_URL/admin/invites" -H 'Content-Type: application/json' \
  -d "$(json_body name=@RUN_LABEL credit_amount_usd=1 expires_in_days=31)" >/dev/null

step "2. Create an invite for \$5"
KEPT_NAME="$RUN_LABEL kept"
export KEPT_NAME
KEPT_BODY="$(request 201 "create an invite" -X POST "$API_URL/admin/invites" \
  -H 'Content-Type: application/json' -d "$(json_body name=@KEPT_NAME credit_amount_usd=5 note='"e2e"')")"
KEPT_URL="$(echo "$KEPT_BODY" | read_json_field invite_url)"
KEPT_CODE="$(echo "$KEPT_URL" | read_code_from_url)"
export KEPT_CODE
pass "link $KEPT_URL"

step "3. Check the code, as the invite page does, signed out"
CHECK_BODY="$(curl -s -X POST "$API_URL/invites/check" -H 'Content-Type: application/json' -d "$(json_body code=@KEPT_CODE)")"
echo "$CHECK_BODY" | print_json >&2
[ "$(echo "$CHECK_BODY" | read_json_field status)" = "UNUSED" ] || fail "expected status UNUSED"
[ "$(echo "$CHECK_BODY" | read_json_field credit_amount_usd)" = "5.0000000000" ] || fail "expected 5.0000000000"
pass "UNUSED, for 5.0000000000"
UNKNOWN_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API_URL/invites/check" -H 'Content-Type: application/json' -d '{"code": "not-a-real-code"}')"
[ "$UNKNOWN_STATUS" = "404" ] || fail "an unknown code: expected 404, got $UNKNOWN_STATUS"
pass "an unknown code → 404"

step "4. The Google login takes a usable code to Google, and refuses an unknown one"
read -r LOGIN_STATUS LOGIN_LOCATION <<<"$(request_redirect "$API_URL/auth/google/login?invite_code=$KEPT_CODE")"
[ "$LOGIN_STATUS" = "307" ] || fail "login with a usable code: expected 307, got $LOGIN_STATUS"
case "$LOGIN_LOCATION" in https://accounts.google.com/*) ;; *) fail "expected a redirect to Google, got $LOGIN_LOCATION" ;; esac
pass "usable code → 307 to Google"
read -r UNKNOWN_LOGIN_STATUS UNKNOWN_LOGIN_LOCATION <<<"$(request_redirect "$API_URL/auth/google/login?invite_code=not-a-real-code")"
[ "$UNKNOWN_LOGIN_STATUS" = "303" ] || fail "login with an unknown code: expected 303, got $UNKNOWN_LOGIN_STATUS"
case "$UNKNOWN_LOGIN_LOCATION" in *"/sign-in?invite_error=INVITE_NOT_FOUND") ;; *) fail "expected invite_error=INVITE_NOT_FOUND, got $UNKNOWN_LOGIN_LOCATION" ;; esac
pass "unknown code → 303 to $UNKNOWN_LOGIN_LOCATION"

step "5. Revoke a second invite"
REVOKED_NAME="$RUN_LABEL revoked"
export REVOKED_NAME
REVOKED_BODY="$(request 201 "create a second invite" -X POST "$API_URL/admin/invites" \
  -H 'Content-Type: application/json' -d "$(json_body name=@REVOKED_NAME credit_amount_usd=1)")"
REVOKED_IDENTITY="$(echo "$REVOKED_BODY" | read_json_field identity)"
REVOKED_CODE="$(echo "$REVOKED_BODY" | read_json_field invite_url | read_code_from_url)"
request 200 "revoke it" -X POST "$API_URL/admin/invites/$REVOKED_IDENTITY/revoke" >/dev/null
request 200 "revoke it again, which changes nothing" -X POST "$API_URL/admin/invites/$REVOKED_IDENTITY/revoke" >/dev/null
request 404 "revoke an unknown invite" -X POST "$API_URL/admin/invites/00000000-0000-0000-0000-000000000000/revoke" >/dev/null
read -r REVOKED_LOGIN_STATUS REVOKED_LOGIN_LOCATION <<<"$(request_redirect "$API_URL/auth/google/login?invite_code=$REVOKED_CODE")"
[ "$REVOKED_LOGIN_STATUS" = "303" ] || fail "login with a revoked code: expected 303, got $REVOKED_LOGIN_STATUS"
case "$REVOKED_LOGIN_LOCATION" in *"invite_error=INVITE_REVOKED") ;; *) fail "expected invite_error=INVITE_REVOKED, got $REVOKED_LOGIN_LOCATION" ;; esac
pass "revoked code → 303 to $REVOKED_LOGIN_LOCATION"

step "6. The admin's list shows both"
INVITE_LIST_BODY="$(request 200 "list invites" "$API_URL/admin/invites")"
[ "$(echo "$INVITE_LIST_BODY" | find_invite_status "$KEPT_NAME")" = "UNUSED" ] || fail "expected the kept invite UNUSED"
[ "$(echo "$INVITE_LIST_BODY" | find_invite_status "$REVOKED_NAME")" = "REVOKED" ] || fail "expected the revoked invite REVOKED"
pass "kept invite UNUSED, revoked invite REVOKED"

printf '\n\033[32mAll steps passed.\033[0m\n'
printf 'To use an invite, open this link with the frontend running and sign in with a Google account:\n  %s\n' "$KEPT_URL"
printf 'Afterwards GET /admin/invites lists it as USED, and the account is a creator with $5.\n'
