#!/usr/bin/env bash
# Walks the admin panel end to end against a running dev server: lists users, reads one
# and their ledger, grants a reader credits, and checks the grant made them a creator and
# signed them out everywhere; then sets them back to a reader, suspends them and
# reactivates them. Prints each response and checks what it can. Run from backend/:
#
#   ./scripts/e2e/admin.sh
#
# It signs in by minting a session for the first admin, so no browser needed. Make your
# user the admin first:
#
#   UPDATE pb_user SET role_id = (SELECT id FROM pb_role WHERE code = 'ADMIN')
#   WHERE email = '<your email>';
#
# It adds a reader with a timestamped email each run, so running it again doesn't
# collide with the last run.
# It refuses to run unless .env points at a local development database.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
READER_EMAIL="e2e-reader-$(date +%Y%m%d%H%M%S)@example.com"
GRANT_NOTE="e2e admin walkthrough"
export READER_EMAIL GRANT_NOTE

# Progress goes to stderr, so a response body captured with $( ) stays clean JSON.
step() { printf '\n\033[1m── %s\033[0m\n' "$1" >&2; }
fail() { printf '\033[31mFAIL\033[0m %s\n' "$1" >&2; exit 1; }
pass() { printf '\033[32m  ok\033[0m %s\n' "$1" >&2; }

# Mints a fresh session for the reader with their current role, as signing in would,
# and prints its id.
mint_reader_session() {
  uv run python - <<'PY'
import asyncio
import os

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.database.orm import RoleOrm, UserOrm
from libs.database.session import create_db_session_factory
from libs.permissions.services import PermissionService


async def main() -> None:
    app_settings = AppSettings()
    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    redis_client = Redis.from_url(app_settings.redis_url)
    try:
        async with db_session_factory() as db_session:
            reader_query = (
                select(UserOrm, RoleOrm.code)
                .join(RoleOrm, RoleOrm.id == UserOrm.role_id)
                .where(UserOrm.email == os.environ["READER_EMAIL"])
            )
            reader_query_result = await db_session.execute(reader_query)
            reader_record, role = reader_query_result.one()
            permission_service = PermissionService(db_session=db_session)
            find_role_permission_list_result = await permission_service.find_role_permission_list(
                role
            )
        reader_auth_user = AuthUser(
            id=reader_record.id,
            identity=reader_record.identity,
            role=role,
            permissions=frozenset(find_role_permission_list_result.permissions),
        )
        auth_session_service = AuthSessionService(
            redis_client=redis_client, auth_settings=app_settings.auth
        )
        reader_session_id = await auth_session_service.create_session(reader_auth_user)
        print(reader_session_id)
    finally:
        await redis_client.aclose()
        await db_engine.dispose()


asyncio.run(main())
PY
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
# Prints the emails in a {"users": [...]} body, in order, one per line.
list_emails() { python3 -c 'import json,sys; [print(u["email"]) for u in json.load(sys.stdin)["users"]]'; }

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

step "Minting an admin session, and adding a reader with two sessions"
SEED_OUTPUT="$(uv run python - <<'PY'
import asyncio
import os

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


async def build_auth_user(db_session, user_record, role) -> AuthUser:
    permission_service = PermissionService(db_session=db_session)
    find_role_permission_list_result = await permission_service.find_role_permission_list(role)
    return AuthUser(
        id=user_record.id,
        identity=user_record.identity,
        role=role,
        permissions=frozenset(find_role_permission_list_result.permissions),
    )


async def main() -> None:
    app_settings = AppSettings()
    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    redis_client = Redis.from_url(app_settings.redis_url)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    try:
        async with db_session_factory() as db_session, db_session.begin():
            # The first admin signs in for the walkthrough
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
            admin_auth_user = await build_auth_user(db_session, admin_record, RoleType.ADMIN)

            # A fresh reader to grant to
            reader_role_query = select(RoleOrm.id).where(RoleOrm.code == RoleType.READER)
            reader_role_id = await db_session.scalar(reader_role_query)
            reader_record = UserOrm(
                email=os.environ["READER_EMAIL"],
                display_name="E2E Reader",
                role_id=reader_role_id,
            )
            db_session.add(reader_record)
            await db_session.flush()
            reader_auth_user = await build_auth_user(db_session, reader_record, RoleType.READER)

            system_user_query = select(UserOrm.identity).where(UserOrm.is_system_user.is_(True))
            system_user_identity = await db_session.scalar(system_user_query)

        admin_session_id = await auth_session_service.create_session(admin_auth_user)
        reader_first_session_id = await auth_session_service.create_session(reader_auth_user)
        reader_second_session_id = await auth_session_service.create_session(reader_auth_user)
        print(admin_session_id)
        print(reader_record.identity)
        print(reader_first_session_id)
        print(reader_second_session_id)
        print(system_user_identity)
        print(admin_record.identity)
    finally:
        await redis_client.aclose()
        await db_engine.dispose()


asyncio.run(main())
PY
)"
SESSION_ID="$(echo "$SEED_OUTPUT" | sed -n 1p)"
READER_IDENTITY="$(echo "$SEED_OUTPUT" | sed -n 2p)"
READER_FIRST_SESSION_ID="$(echo "$SEED_OUTPUT" | sed -n 3p)"
READER_SECOND_SESSION_ID="$(echo "$SEED_OUTPUT" | sed -n 4p)"
SYSTEM_USER_IDENTITY="$(echo "$SEED_OUTPUT" | sed -n 5p)"
ADMIN_IDENTITY="$(echo "$SEED_OUTPUT" | sed -n 6p)"
pass "admin session ready; reader $READER_EMAIL has two sessions"

step "1. The reader is signed in on both sessions"
for READER_SESSION_ID in "$READER_FIRST_SESSION_ID" "$READER_SECOND_SESSION_ID"; do
  READER_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -b "sid=$READER_SESSION_ID" "$API_URL/users/me")"
  [ "$READER_STATUS" = "200" ] || fail "reader session before the grant: expected 200, got $READER_STATUS"
done
pass "both reader sessions → 200"

step "2. A reader can't use the admin routes"
READER_ADMIN_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -b "sid=$READER_FIRST_SESSION_ID" "$API_URL/admin/users")"
[ "$READER_ADMIN_STATUS" = "403" ] || fail "reader listing users: expected 403, got $READER_ADMIN_STATUS"
pass "reader listing users → 403"

step "3. List users — the new reader is first, as the newest"
USER_LIST_BODY="$(request 200 "list users" "$API_URL/admin/users")"
[ "$(echo "$USER_LIST_BODY" | list_emails | head -1)" = "$READER_EMAIL" ] \
  || fail "expected $READER_EMAIL listed first"
pass "$READER_EMAIL is listed first"

step "4. Read the reader, and their empty ledger"
USER_BODY="$(request 200 "read the reader" "$API_URL/admin/users/$READER_IDENTITY")"
[ "$(echo "$USER_BODY" | read_json_field role)" = "READER" ] || fail "expected role READER"
pass "role is READER"
LEDGER_BODY="$(request 200 "read their ledger" "$API_URL/admin/users/$READER_IDENTITY/credit-ledger")"
[ "$(echo "$LEDGER_BODY" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["credit_ledger_entries"]))')" = "0" ] \
  || fail "expected an empty ledger"
pass "ledger is empty"

step "5. Grants that are refused"
request 422 "an amount of 0" -X POST "$API_URL/admin/users/$READER_IDENTITY/credit-grants" \
  -H 'Content-Type: application/json' -d "$(json_body amount_usd=0 note=@GRANT_NOTE)" >/dev/null
request 422 "an amount above \$100" -X POST "$API_URL/admin/users/$READER_IDENTITY/credit-grants" \
  -H 'Content-Type: application/json' -d "$(json_body amount_usd=100.01 note=@GRANT_NOTE)" >/dev/null
request 409 "the system user" -X POST "$API_URL/admin/users/$SYSTEM_USER_IDENTITY/credit-grants" \
  -H 'Content-Type: application/json' -d "$(json_body amount_usd=1 note=@GRANT_NOTE)" >/dev/null
request 404 "an unknown user" -X POST "$API_URL/admin/users/00000000-0000-0000-0000-000000000000/credit-grants" \
  -H 'Content-Type: application/json' -d "$(json_body amount_usd=1 note=@GRANT_NOTE)" >/dev/null

step "6. Grant the reader \$2.50"
request 201 "grant \$2.50" -X POST "$API_URL/admin/users/$READER_IDENTITY/credit-grants" \
  -H 'Content-Type: application/json' -d "$(json_body amount_usd=2.5 note=@GRANT_NOTE)" >/dev/null
GRANTED_BODY="$(request 200 "read the reader again" "$API_URL/admin/users/$READER_IDENTITY")"
[ "$(echo "$GRANTED_BODY" | read_json_field role)" = "CREATOR" ] || fail "expected role CREATOR"
[ "$(echo "$GRANTED_BODY" | read_json_field credit_balance_usd)" = "2.5000000000" ] \
  || fail "expected a balance of 2.5000000000"
pass "now a CREATOR with \$2.50"

step "7. The grant signed the reader out everywhere"
for READER_SESSION_ID in "$READER_FIRST_SESSION_ID" "$READER_SECOND_SESSION_ID"; do
  READER_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -b "sid=$READER_SESSION_ID" "$API_URL/users/me")"
  [ "$READER_STATUS" = "401" ] || fail "reader session after the grant: expected 401, got $READER_STATUS"
done
pass "both old sessions → 401, so they sign in again as a creator"

step "8. The ledger shows the grant, made by the admin"
GRANT_LEDGER_BODY="$(request 200 "read their ledger" "$API_URL/admin/users/$READER_IDENTITY/credit-ledger")"
echo "$GRANT_LEDGER_BODY" | python3 -c '
import json, os, sys

entries = json.load(sys.stdin)["credit_ledger_entries"]
assert len(entries) == 1, f"expected one row, got {len(entries)}"
assert entries[0]["entry_type"] == "GRANT", entries[0]["entry_type"]
assert entries[0]["amount_usd"] == "2.5000000000", entries[0]["amount_usd"]
assert entries[0]["note"] == os.environ["GRANT_NOTE"], entries[0]["note"]
' || fail "the ledger doesn't hold the one grant"
pass "one GRANT of 2.5000000000 with the note"

step "9. Role and suspension changes that are refused"
request 422 "making someone an admin" -X PUT "$API_URL/admin/users/$READER_IDENTITY/role" \
  -H 'Content-Type: application/json' -d "$(json_body role='"ADMIN"')" >/dev/null
request 409 "changing an admin's role" -X PUT "$API_URL/admin/users/$ADMIN_IDENTITY/role" \
  -H 'Content-Type: application/json' -d "$(json_body role='"READER"')" >/dev/null
request 409 "suspending an admin" -X PUT "$API_URL/admin/users/$ADMIN_IDENTITY/active" \
  -H 'Content-Type: application/json' -d "$(json_body is_active=false)" >/dev/null
request 404 "the system user" -X PUT "$API_URL/admin/users/$SYSTEM_USER_IDENTITY/active" \
  -H 'Content-Type: application/json' -d "$(json_body is_active=false)" >/dev/null

step "10. Set the creator back to a reader, which signs them out"
CREATOR_SESSION_ID="$(mint_reader_session)"
request 200 "set the role to READER" -X PUT "$API_URL/admin/users/$READER_IDENTITY/role" \
  -H 'Content-Type: application/json' -d "$(json_body role='"READER"')" >/dev/null
DEMOTED_BODY="$(request 200 "read the user again" "$API_URL/admin/users/$READER_IDENTITY")"
[ "$(echo "$DEMOTED_BODY" | read_json_field role)" = "READER" ] || fail "expected role READER"
CREATOR_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -b "sid=$CREATOR_SESSION_ID" "$API_URL/users/me")"
[ "$CREATOR_STATUS" = "401" ] || fail "creator session after the demotion: expected 401, got $CREATOR_STATUS"
pass "a READER again, and their creator session → 401"

step "11. Suspend them, which signs them out"
SUSPENDED_SESSION_ID="$(mint_reader_session)"
request 200 "suspend" -X PUT "$API_URL/admin/users/$READER_IDENTITY/active" \
  -H 'Content-Type: application/json' -d "$(json_body is_active=false)" >/dev/null
request 200 "suspend again, which changes nothing" -X PUT "$API_URL/admin/users/$READER_IDENTITY/active" \
  -H 'Content-Type: application/json' -d "$(json_body is_active=false)" >/dev/null
SUSPENDED_BODY="$(request 200 "read the user again" "$API_URL/admin/users/$READER_IDENTITY")"
[ "$(echo "$SUSPENDED_BODY" | read_json_field is_active)" = "False" ] || fail "expected is_active false"
SUSPENDED_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -b "sid=$SUSPENDED_SESSION_ID" "$API_URL/users/me")"
[ "$SUSPENDED_STATUS" = "401" ] || fail "session after the suspension: expected 401, got $SUSPENDED_STATUS"
pass "suspended, and their session → 401"

step "12. Reactivate them"
request 200 "reactivate" -X PUT "$API_URL/admin/users/$READER_IDENTITY/active" \
  -H 'Content-Type: application/json' -d "$(json_body is_active=true)" >/dev/null
REACTIVATED_BODY="$(request 200 "read the user again" "$API_URL/admin/users/$READER_IDENTITY")"
[ "$(echo "$REACTIVATED_BODY" | read_json_field is_active)" = "True" ] || fail "expected is_active true"
pass "active again, still a $(echo "$REACTIVATED_BODY" | read_json_field role)"

printf '\n\033[32mAll steps passed.\033[0m The user %s stays in the database as an active reader.\n' "$READER_EMAIL"
