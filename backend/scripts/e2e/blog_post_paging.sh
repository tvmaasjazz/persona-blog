#!/usr/bin/env bash
# Walks paging, sorting, filtering and search end to end against a running dev server,
# on the open page of a persona's posts (GET /blog-posts/public). Writes a public persona
# with five published public posts, a draft and a private post, then checks pages and
# their totals, both sorts, search by title and subtitle (never the body), what a
# signed-out reader, a second user and the owner each see, and the 422s for a bad page or
# sort. Prints each response and checks what it can. Run from backend/:
#
#   ./scripts/e2e/blog_post_paging.sh
#
# It signs in as the first non-system user, and as a dedicated second user
# (verify-second-user@persona-blog.invalid) that it creates in the local database the
# first time it runs. Each run writes a new persona, so it can run again. No LLM calls.
# It refuses to run unless .env points at a local development database.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
RUN_SUFFIX="$(date +%H%M%S)"
# Exported so the json_body python below can read them from os.environ.
PERSONA_NAME="Paging Pat $RUN_SUFFIX"
PERSONA_BIO="Bakes, writes, and keeps far too many drafts."
POST_BODY="A paragraph to open the post."
# A word only a body holds, to check search skips the body
BODY_ONLY_WORD="zymurgy"
iso_seconds_ago() { python3 -c "from datetime import UTC, datetime, timedelta; print((datetime.now(UTC) - timedelta(seconds=$1)).isoformat())"; }
export PERSONA_NAME PERSONA_BIO POST_BODY BODY_ONLY_WORD

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

step "Checking the server has the paged route"
if ! curl -sf --max-time 3 "$API_URL/openapi.json" | grep -q '"/blog-posts/public"'; then
  fail "the server at $API_URL has no GET /blog-posts/public — it's running older code; restart it with: uv run granian --interface asgi apps.api.main:app --reload"
fi
pass "GET /blog-posts/public is served"

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
# Evaluates a python expression over the JSON on stdin, bound to d.
json_eval() { python3 -c 'import json, sys; d = json.load(sys.stdin); print(eval(sys.argv[1]))' "$1"; }
titles() { json_eval '",".join(row["title"].split(" ")[0] for row in d["blog_posts"])'; }
total() { json_eval 'd["pagination"]["total"]'; }

create_post() {
  local title="$1" is_public="$2" published_at="$3" subtitle="$4" body="$5" payload
  # json_body reads @NAME values from the environment
  export POST_TITLE="$title" POST_SUBTITLE="$subtitle" POST_PUBLISHED_AT="$published_at" POST_TEXT="$body"
  if [ -n "$published_at" ]; then
    payload="$(json_body persona_identity=@PERSONA_IDENTITY title=@POST_TITLE subtitle=@POST_SUBTITLE \
      body=@POST_TEXT is_public="$is_public" published_at=@POST_PUBLISHED_AT)"
  else
    payload="$(json_body persona_identity=@PERSONA_IDENTITY title=@POST_TITLE subtitle=@POST_SUBTITLE \
      body=@POST_TEXT is_public="$is_public" published_at=null)"
  fi
  request "$OWNER_SESSION" 201 "create $title" -X POST "$API_URL/blog-posts" \
    -H 'Content-Type: application/json' -d "$payload" >/dev/null
}

# Fetches a page of the persona's posts signed out; extra arguments are query params.
fetch_page_signed_out() {
  local description="$1"
  shift
  local params=(--data-urlencode "persona_identity=$PERSONA_IDENTITY")
  for param in "$@"; do params+=(--data-urlencode "$param"); done
  request_signed_out 200 "$description" -G "$API_URL/blog-posts/public" "${params[@]}"
}

expect() {
  local actual="$1" expected="$2" description="$3"
  [ "$actual" = "$expected" ] || fail "$description: expected $expected, got $actual"
  pass "$description: $actual"
}

step "1. Create a public persona"
PERSONA_BODY="$(request "$OWNER_SESSION" 201 "create persona" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@PERSONA_NAME bio=@PERSONA_BIO is_public=true)")"
PERSONA_IDENTITY="$(echo "$PERSONA_BODY" | read_json_field identity)"
export PERSONA_IDENTITY

step "2. Write five published public posts, a draft and a private post"
# Oldest first; the first word of each title is what the checks below compare.
create_post "Alpha Rye Loaf" true "$(iso_seconds_ago 70)" "Crumb notes" "$POST_BODY"
create_post "Bravo Spelt Crackers" true "$(iso_seconds_ago 60)" "" "$POST_BODY"
create_post "Charlie Rye Crackers" true "$(iso_seconds_ago 50)" "" "$POST_BODY"
create_post "Delta Hydration at 100%" true "$(iso_seconds_ago 40)" "" "$POST_BODY"
create_post "Echo Starter Care" true "$(iso_seconds_ago 30)" "" "A word on $BODY_ONLY_WORD."
create_post "Foxtrot Draft" false "" "" "$POST_BODY"
create_post "Golf Private" false "$(iso_seconds_ago 20)" "" "$POST_BODY"

step "3. Page through signed out, two at a time, newest first"
PAGE="$(fetch_page_signed_out "page 1" page=1 page_size=2)"
expect "$(echo "$PAGE" | titles)" "Echo,Delta" "page 1 titles"
expect "$(echo "$PAGE" | total)" "5" "total, without the draft and the private post"
expect "$(echo "$PAGE" | json_eval 'any("body" in row for row in d["blog_posts"])')" "False" "a row carries a body"
PAGE="$(fetch_page_signed_out "page 2" page=2 page_size=2)"
expect "$(echo "$PAGE" | titles)" "Charlie,Bravo" "page 2 titles"
PAGE="$(fetch_page_signed_out "page 3" page=3 page_size=2)"
expect "$(echo "$PAGE" | titles)" "Alpha" "page 3 titles"
PAGE="$(fetch_page_signed_out "page 4, past the end" page=4 page_size=2)"
expect "$(echo "$PAGE" | json_eval 'len(d["blog_posts"])')" "0" "rows past the end"
expect "$(echo "$PAGE" | total)" "5" "total past the end"

step "4. Sort by title"
PAGE="$(fetch_page_signed_out "title A to Z" sort_by=TITLE sort_direction=ASC)"
expect "$(echo "$PAGE" | titles)" \
  "Alpha,Bravo,Charlie,Delta,Echo" "title A to Z"
PAGE="$(fetch_page_signed_out "title Z to A" sort_by=TITLE sort_direction=DESC)"
expect "$(echo "$PAGE" | titles)" \
  "Echo,Delta,Charlie,Bravo,Alpha" "title Z to A"

step "5. Search the title and subtitle, never the body"
PAGE="$(fetch_page_signed_out "search rye" search=rye)"
expect "$(echo "$PAGE" | titles)" "Charlie,Alpha" "\"rye\""
PAGE="$(fetch_page_signed_out "search RYE" search=RYE)"
expect "$(echo "$PAGE" | titles)" "Charlie,Alpha" "\"RYE\", ignoring case"
PAGE="$(fetch_page_signed_out "search rye crackers" "search=rye crackers")"
expect "$(echo "$PAGE" | titles)" "Charlie" "\"rye crackers\", every word"
PAGE="$(fetch_page_signed_out "search a subtitle word" search=crumb)"
expect "$(echo "$PAGE" | titles)" "Alpha" "\"crumb\", in a subtitle"
PAGE="$(fetch_page_signed_out "search a body-only word" "search=$BODY_ONLY_WORD")"
expect "$(echo "$PAGE" | total)" "0" "\"$BODY_ONLY_WORD\", only in a body"
PAGE="$(fetch_page_signed_out "search %" search=%)"
expect "$(echo "$PAGE" | titles)" "Delta" "\"%\", matched as itself"

step "6. The owner sees their draft and private post too; a second user doesn't"
OWNER_PAGE="$(request "$OWNER_SESSION" 200 "owner lists the persona" -G "$API_URL/blog-posts/public" \
  --data-urlencode "persona_identity=$PERSONA_IDENTITY")"
expect "$(echo "$OWNER_PAGE" | total)" "7" "owner's total"
expect "$(echo "$OWNER_PAGE" | titles)" "Golf,Echo,Delta,Charlie,Bravo,Alpha,Foxtrot" \
  "owner's order, the unpublished draft last"
OTHER_PAGE="$(request "$OTHER_SESSION" 200 "second user lists the persona" -G "$API_URL/blog-posts/public" \
  --data-urlencode "persona_identity=$PERSONA_IDENTITY")"
expect "$(echo "$OTHER_PAGE" | total)" "5" "second user's total"

step "7. A bad page, page size or sort is a 422"
request_signed_out 422 "page 0" -G "$API_URL/blog-posts/public" --data-urlencode page=0 >/dev/null
request_signed_out 422 "page_size 101" -G "$API_URL/blog-posts/public" --data-urlencode page_size=101 >/dev/null
request_signed_out 422 "sort_by a column the route doesn't allow" -G "$API_URL/blog-posts/public" \
  --data-urlencode sort_by=CREATED_AT >/dev/null
request_signed_out 422 "a malformed persona_identity" -G "$API_URL/blog-posts/public" \
  --data-urlencode persona_identity=not-a-uuid >/dev/null

step "8. With no persona, it lists every post the caller may see"
request_signed_out 200 "signed out lists every public post" "$API_URL/blog-posts/public" >/dev/null

printf '\n\033[32mAll steps passed.\033[0m\n'
