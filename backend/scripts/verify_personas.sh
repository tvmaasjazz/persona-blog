#!/usr/bin/env bash
# Walks persona CRUD end to end against a running dev server: creates two personas,
# lists them, reads one, updates one, and soft deletes the other. Prints each response
# and checks what it can. Run from backend/:
#
#   ./scripts/verify_personas.sh
#
# It signs in by minting a session for the first non-system user, so no browser needed.
# It refuses to run unless .env points at a local development database.
# Persona names carry a timestamp, so running it again doesn't collide with the last run.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
RUN_SUFFIX="$(date +%H%M%S)"
# Exported so the json_body python below can read them from os.environ.
FIRST_NAME="Marta Quill $RUN_SUFFIX"
FIRST_BIO="Home baker who writes plainly about bread and the science under it."
FIRST_RENAMED="Marta Quill, Baker $RUN_SUFFIX"
SECOND_NAME="Dev Ashford $RUN_SUFFIX"
SECOND_BIO="Ex-sysadmin with strong opinions about boring technology."
FIRST_STYLE="Short sentences, no jargon, one joke per post at most."
FIRST_TONE="warm, practical"
export FIRST_NAME FIRST_BIO FIRST_RENAMED SECOND_NAME SECOND_BIO FIRST_STYLE FIRST_TONE

# Progress goes to stderr, so a response body captured with $( ) stays clean JSON.
step() { printf '\n\033[1m── %s\033[0m\n' "$1" >&2; }
fail() { printf '\033[31mFAIL\033[0m %s\n' "$1" >&2; exit 1; }
pass() { printf '\033[32m  ok\033[0m %s\n' "$1" >&2; }

read_json_field() { python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
# Builds a JSON object from key=value pairs: @NAME reads environment variable NAME as
# a string, anything else is parsed as a JSON literal. See verify_generate_text.sh for
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
# Prints the names in a {"personas": [...]} body, in order, one per line.
list_names() { python3 -c 'import json,sys; [print(p["name"]) for p in json.load(sys.stdin)["personas"]]'; }

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

step "Minting a session for the first non-system user"
SESSION_ID="$(uv run python - <<'PY'
import asyncio

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from libs.auth.services import AuthSessionService
from libs.database.orm import UserOrm
from libs.database.session import create_db_session_factory


async def main() -> None:
    app_settings = AppSettings()
    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    async with db_session_factory() as db_session:
        user_query = select(UserOrm).where(UserOrm.is_system_user.is_(False)).order_by(UserOrm.id)
        user_record = await db_session.scalar(user_query)
    if user_record is None:
        await db_engine.dispose()
        raise SystemExit("no signed-in user yet — visit /auth/google/login in a browser first")

    redis_client = Redis.from_url(app_settings.redis_url)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    session_id = await auth_session_service.create_session(user_record.id, user_record.identity)
    print(session_id)
    await redis_client.aclose()
    await db_engine.dispose()


asyncio.run(main())
PY
)"
pass "session ready"

step "1. Create two personas — the first private, the second public"
FIRST_BODY="$(request 201 "create '$FIRST_NAME'" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@FIRST_NAME bio=@FIRST_BIO writing_style=@FIRST_STYLE \
        default_tone=@FIRST_TONE is_public=false)")"
FIRST_IDENTITY="$(echo "$FIRST_BODY" | read_json_field identity)"
SECOND_BODY="$(request 201 "create '$SECOND_NAME'" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@SECOND_NAME bio=@SECOND_BIO is_public=true)")"
SECOND_IDENTITY="$(echo "$SECOND_BODY" | read_json_field identity)"

step "2. Creating a third with a name already taken is refused"
request 409 "duplicate name" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@FIRST_NAME bio=@FIRST_BIO)" >/dev/null

step "3. List — both appear, newest first"
LIST_BODY="$(request 200 "list your personas" "$API_URL/personas")"
LIST_NAMES="$(echo "$LIST_BODY" | list_names)"
[ "$(echo "$LIST_NAMES" | grep -nxF "$SECOND_NAME" | cut -d: -f1)" -lt \
  "$(echo "$LIST_NAMES" | grep -nxF "$FIRST_NAME" | cut -d: -f1)" ] \
  || fail "expected '$SECOND_NAME' listed before '$FIRST_NAME'"
pass "'$SECOND_NAME' is listed before '$FIRST_NAME'"

step "4. Read the first persona"
READ_BODY="$(request 200 "read '$FIRST_NAME'" "$API_URL/personas/$FIRST_IDENTITY")"
[ "$(echo "$READ_BODY" | read_json_field name)" = "$FIRST_NAME" ] || fail "read back the wrong persona"
pass "read back '$FIRST_NAME'"

step "5. Update the first persona — rename it and make it public"
request 200 "update '$FIRST_NAME'" -X PUT "$API_URL/personas/$FIRST_IDENTITY" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@FIRST_RENAMED bio=@FIRST_BIO writing_style=@FIRST_STYLE \
        default_tone=@FIRST_TONE is_public=true)" >/dev/null
UPDATED_BODY="$(request 200 "read it back" "$API_URL/personas/$FIRST_IDENTITY")"
[ "$(echo "$UPDATED_BODY" | read_json_field name)" = "$FIRST_RENAMED" ] || fail "the rename didn't stick"
[ "$(echo "$UPDATED_BODY" | read_json_field is_public)" = "True" ] || fail "is_public didn't stick"
pass "renamed to '$FIRST_RENAMED' and public"

step "6. Soft delete the second persona"
request 200 "delete '$SECOND_NAME'" -X DELETE "$API_URL/personas/$SECOND_IDENTITY" >/dev/null
request 404 "reading it now" "$API_URL/personas/$SECOND_IDENTITY" >/dev/null
RELIST_BODY="$(request 200 "list again" "$API_URL/personas")"
if echo "$RELIST_BODY" | list_names | grep -qxF "$SECOND_NAME"; then
  fail "'$SECOND_NAME' is still listed"
fi
pass "'$SECOND_NAME' is gone from the list"

step "7. Signed out is refused"
SIGNED_OUT_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/personas")"
[ "$SIGNED_OUT_STATUS" = "401" ] || fail "listing while signed out: expected 401, got $SIGNED_OUT_STATUS"
pass "listing while signed out → 401"

step "8. What the table holds for these two"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT name, is_public, created_at, updated_at, deleted_at IS NOT NULL AS is_deleted
   FROM pb_persona WHERE identity IN ('$FIRST_IDENTITY', '$SECOND_IDENTITY') ORDER BY created_at;"

printf '\n\033[32mAll steps passed.\033[0m The deleted persona keeps its row, with deleted_at set.\n'
