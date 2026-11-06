#!/usr/bin/env bash
# Walks reading signed out end to end against a running dev server: a persona and a post
# each have an owner-only route and an open /public one. Checks what a signed-out reader,
# a second user and the owner each see, that making the persona private hides its posts
# from others without changing them, and that the owner can still edit a public post
# under a private persona. Prints each response and checks what it can. Run from
# backend/:
#
#   ./scripts/e2e/reading_signed_out.sh
#
# It signs in as the first non-system user, and as a dedicated second user
# (verify-second-user@persona-blog.invalid) that it creates in the local database the
# first time it runs. Names carry a timestamp, so it can run again. No LLM calls.
# It refuses to run unless .env points at a local development database.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
RUN_SUFFIX="$(date +%H%M%S)"
# Exported so the json_body python below can read them from os.environ.
PERSONA_NAME="Marta Quill $RUN_SUFFIX"
PERSONA_BIO="Home baker who writes plainly about bread and the science under it."
PERSONA_BACKGROUND="Grew up above her parents' bakery."
PUBLIC_POST_TITLE="Notes From a Slow Morning $RUN_SUFFIX"
PUBLIC_POST_TITLE_EDITED="Notes From a Slower Morning $RUN_SUFFIX"
PRIVATE_POST_TITLE="Drafts I Keep $RUN_SUFFIX"
POST_BODY="A paragraph to open the post."
NOW_ISO="$(python3 -c 'from datetime import UTC, datetime; print(datetime.now(UTC).isoformat())')"
export PERSONA_NAME PERSONA_BIO PERSONA_BACKGROUND PUBLIC_POST_TITLE PUBLIC_POST_TITLE_EDITED \
  PRIVATE_POST_TITLE POST_BODY NOW_ISO

# Progress goes to stderr, so a response body captured with $( ) stays clean JSON.
step() { printf '\n\033[1m── %s\033[0m\n' "$1" >&2; }
fail() { printf '\033[31mFAIL\033[0m %s\n' "$1" >&2; exit 1; }
pass() { printf '\033[32m  ok\033[0m %s\n' "$1" >&2; }

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

# Sends a request as the session in $1, shows the body, and prints it for capture; fails
# unless the status matches. Capture it into a variable before piping: inside a pipeline,
# fail only exits the pipeline's subshell.
request() {
  local session_id="$1" expected="$2" description="$3" response status body
  shift 3
  response="$(curl -s -w '\n%{http_code}' -b "sid=$session_id" "$@")"
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

step "Minting sessions for you and for the second user"
SESSION_IDS="$(uv run python - <<'PY'
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

SECOND_USER_EMAIL = "verify-second-user@persona-blog.invalid"


async def build_auth_user(db_session_factory, user_record) -> AuthUser:
    async with db_session_factory() as db_session:
        role_query = select(RoleOrm.code).where(RoleOrm.id == user_record.role_id)
        role = await db_session.scalar(role_query)
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
    async with db_session_factory() as db_session, db_session.begin():
        first_user_query = (
            select(UserOrm)
            .where(UserOrm.is_system_user.is_(False), UserOrm.email != SECOND_USER_EMAIL)
            .order_by(UserOrm.id)
        )
        first_user_record = await db_session.scalar(first_user_query)
        if first_user_record is None:
            raise SystemExit("no signed-in user yet — visit /auth/google/login in a browser first")

        second_user_query = select(UserOrm).where(UserOrm.email == SECOND_USER_EMAIL)
        second_user_record = await db_session.scalar(second_user_query)
        if second_user_record is None:
            # A creator, so the checks reach ownership rather than stopping at permissions
            creator_role_query = select(RoleOrm.id).where(RoleOrm.code == RoleType.CREATOR)
            creator_role_id = await db_session.scalar(creator_role_query)
            second_user_record = UserOrm(
                email=SECOND_USER_EMAIL, display_name="Verify Second User", role_id=creator_role_id
            )
            db_session.add(second_user_record)
            await db_session.flush()

    redis_client = Redis.from_url(app_settings.redis_url)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    for user_record in (first_user_record, second_user_record):
        auth_user = await build_auth_user(db_session_factory, user_record)
        session_id = await auth_session_service.create_session(auth_user)
        print(session_id)
    await redis_client.aclose()
    await db_engine.dispose()


asyncio.run(main())
PY
)"

OWNER_SESSION="$(echo "$SESSION_IDS" | sed -n 1p)"
OTHER_SESSION="$(echo "$SESSION_IDS" | sed -n 2p)"
pass "two sessions ready"

# Sends a request with no session cookie at all.
request_signed_out() {
  local expected="$1" description="$2" response status body
  shift 2
  response="$(curl -s -w '\n%{http_code}' "$@")"
  status="${response##*$'\n'}"
  body="${response%$'\n'*}"
  if [ -n "$body" ]; then echo "$body" | print_json >&2 2>/dev/null || echo "$body" >&2; fi
  [ "$status" = "$expected" ] || fail "$description: expected $expected, got $status"
  pass "$description → $expected"
  echo "$body"
}
has_json_field() { python3 -c "import json,sys; print('$1' in json.load(sys.stdin))"; }

update_persona() {
  local is_public="$1" description="$2"
  request "$OWNER_SESSION" 200 "$description" -X PUT "$API_URL/personas/$PERSONA_IDENTITY" \
    -H 'Content-Type: application/json' \
    -d "$(json_body name=@PERSONA_NAME bio=@PERSONA_BIO background=@PERSONA_BACKGROUND \
          is_public="$is_public")" >/dev/null
}

step "1. Create a public persona with a background"
PERSONA_BODY="$(request "$OWNER_SESSION" 201 "create persona" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@PERSONA_NAME bio=@PERSONA_BIO background=@PERSONA_BACKGROUND is_public=true)")"
PERSONA_IDENTITY="$(echo "$PERSONA_BODY" | read_json_field identity)"
export PERSONA_IDENTITY

step "2. Read the persona signed out — the public fields only"
PUBLIC_PERSONA="$(request_signed_out 200 "signed out reads /public" "$API_URL/personas/$PERSONA_IDENTITY/public")"
[ "$(echo "$PUBLIC_PERSONA" | read_json_field bio)" = "$PERSONA_BIO" ] || fail "the bio is missing"
[ "$(echo "$PUBLIC_PERSONA" | has_json_field background)" = "False" ] || fail "the background reached a reader"
[ "$(echo "$PUBLIC_PERSONA" | read_json_field is_owner)" = "False" ] || fail "a signed-out reader is_owner"
pass "bio shown, background hidden, is_owner false"

step "3. The owner on /public is the owner; a second user can't use the owner's route"
OWNER_PUBLIC_PERSONA="$(request "$OWNER_SESSION" 200 "owner reads /public" "$API_URL/personas/$PERSONA_IDENTITY/public")"
[ "$(echo "$OWNER_PUBLIC_PERSONA" | read_json_field is_owner)" = "True" ] || fail "the owner isn't is_owner"
pass "is_owner true for the owner"
request "$OTHER_SESSION" 404 "second user reads the owner's route" "$API_URL/personas/$PERSONA_IDENTITY" >/dev/null
OWNER_PERSONA="$(request "$OWNER_SESSION" 200 "owner reads the owner's route" "$API_URL/personas/$PERSONA_IDENTITY")"
[ "$(echo "$OWNER_PERSONA" | read_json_field background)" = "$PERSONA_BACKGROUND" ] \
  || fail "the owner's route doesn't return the background"
pass "the owner's route returns every field"

step "4. Write a published public post and a private one"
PUBLIC_POST_BODY="$(request "$OWNER_SESSION" 201 "create public post" -X POST "$API_URL/blog-posts" \
  -H 'Content-Type: application/json' \
  -d "$(json_body persona_identity=@PERSONA_IDENTITY title=@PUBLIC_POST_TITLE body=@POST_BODY \
        is_public=true published_at=@NOW_ISO)")"
PUBLIC_POST_IDENTITY="$(echo "$PUBLIC_POST_BODY" | read_json_field identity)"
PRIVATE_POST_BODY="$(request "$OWNER_SESSION" 201 "create private post" -X POST "$API_URL/blog-posts" \
  -H 'Content-Type: application/json' \
  -d "$(json_body persona_identity=@PERSONA_IDENTITY title=@PRIVATE_POST_TITLE body=@POST_BODY \
        is_public=false published_at=@NOW_ISO)")"
PRIVATE_POST_IDENTITY="$(echo "$PRIVATE_POST_BODY" | read_json_field identity)"

step "5. Read the posts signed out and as a second user"
SIGNED_OUT_POST="$(request_signed_out 200 "signed out reads the public post" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY/public")"
[ "$(echo "$SIGNED_OUT_POST" | read_json_field is_owner)" = "False" ] || fail "a signed-out reader is_owner"
request "$OTHER_SESSION" 200 "second user reads the public post" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY/public" >/dev/null
request_signed_out 404 "signed out reads the private post" "$API_URL/blog-posts/$PRIVATE_POST_IDENTITY/public" >/dev/null
request "$OTHER_SESSION" 404 "second user reads the owner's route" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY" >/dev/null
OWNER_PRIVATE_POST="$(request "$OWNER_SESSION" 200 "owner reads the private post on /public" "$API_URL/blog-posts/$PRIVATE_POST_IDENTITY/public")"
[ "$(echo "$OWNER_PRIVATE_POST" | read_json_field is_owner)" = "True" ] || fail "the owner isn't is_owner"

step "6. Make the persona private — it and its public post are hidden from others"
update_persona false "make the persona private"
request_signed_out 404 "signed out reads the private persona" "$API_URL/personas/$PERSONA_IDENTITY/public" >/dev/null
request_signed_out 404 "signed out reads its public post" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY/public" >/dev/null
request "$OTHER_SESSION" 404 "second user reads its public post" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY/public" >/dev/null
HIDDEN_POST="$(request "$OWNER_SESSION" 200 "owner still reads it" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY")"
[ "$(echo "$HIDDEN_POST" | read_json_field is_public)" = "True" ] || fail "the post's is_public changed"
pass "the post keeps is_public true"

step "7. The owner edits the public post under the private persona"
request "$OWNER_SESSION" 200 "edit it, keeping it public" -X PUT "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY" \
  -H 'Content-Type: application/json' \
  -d "$(json_body title=@PUBLIC_POST_TITLE_EDITED body=@POST_BODY is_public=true published_at=@NOW_ISO)" >/dev/null
request "$OWNER_SESSION" 422 "make the private post public" -X PUT "$API_URL/blog-posts/$PRIVATE_POST_IDENTITY" \
  -H 'Content-Type: application/json' \
  -d "$(json_body title=@PRIVATE_POST_TITLE body=@POST_BODY is_public=true published_at=@NOW_ISO)" >/dev/null

step "8. Make the persona public again — exactly the public post comes back"
update_persona true "make the persona public"
BACK_POST="$(request_signed_out 200 "signed out reads the public post" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY/public")"
[ "$(echo "$BACK_POST" | read_json_field title)" = "$PUBLIC_POST_TITLE_EDITED" ] || fail "the edit didn't stick"
request_signed_out 404 "signed out reads the private post" "$API_URL/blog-posts/$PRIVATE_POST_IDENTITY/public" >/dev/null

step "9. An expired session is a 401, not signed out"
EXPIRED_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -b "sid=not-a-real-session" "$API_URL/personas/$PERSONA_IDENTITY/public")"
[ "$EXPIRED_STATUS" = "401" ] || fail "an expired session on /public: expected 401, got $EXPIRED_STATUS"
pass "expired session on /public → 401"

step "10. The owner's routes still need signing in"
request_signed_out 401 "signed out reads the owner's persona route" "$API_URL/personas/$PERSONA_IDENTITY" >/dev/null
request_signed_out 401 "signed out reads the owner's post route" "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY" >/dev/null
request_signed_out 401 "signed out lists posts" "$API_URL/blog-posts" >/dev/null

printf '\n\033[32mAll steps passed.\033[0m\n'
