#!/usr/bin/env bash
# Walks post views and the feed score end to end against a running dev server: a
# published public post is viewed signed out, by a second signed-in user and by its
# owner. Checks that a view counts once per reader per day, that only further reading
# adds to engagement, that a different browser is a different signed-out reader, that
# the owner's views aren't recorded, and that the score rises with engagement. Prints
# each response and the post's engagement row, and checks what it can. Run from
# backend/:
#
#   ./scripts/e2e/content_item_views.sh
#
# It signs in as the first non-system user, and as a dedicated second user
# (verify-second-user@personagora.invalid) that it creates in the local database the
# first time it runs. Names carry a timestamp, so it can run again. No LLM calls.
# It refuses to run unless .env points at a local development database.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
RUN_SUFFIX="$(date +%H%M%S)"
# Exported so the json_body python below can read them from os.environ.
PERSONA_NAME="Odile Marsh $RUN_SUFFIX"
PERSONA_BIO="Retired cartographer who writes about maps and the people who draw them."
PUBLIC_POST_TITLE="Where the Coastline Ends $RUN_SUFFIX"
PRIVATE_POST_TITLE="Unfinished Survey $RUN_SUFFIX"
POST_BODY="A paragraph to open the post."
NOW_ISO="$(python3 -c 'from datetime import UTC, datetime; print(datetime.now(UTC).isoformat())')"
# Two signed-out readers, told apart by their browser
FIRST_BROWSER="blog-post-views-e2e/first-browser"
SECOND_BROWSER="blog-post-views-e2e/second-browser"
export PERSONA_NAME PERSONA_BIO PUBLIC_POST_TITLE PRIVATE_POST_TITLE POST_BODY NOW_ISO

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

SECOND_USER_EMAIL = "verify-second-user@personagora.invalid"


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

# Reads the post's engagement row and its views from the local database, as
# "view_count read_percent_sum feed_score view_rows anonymous_view_rows".
read_engagement() {
  BLOG_POST_IDENTITY="$1" uv run python - <<'PY'
import asyncio
import os
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from libs.database.orm import BlogPostOrm, ContentItemEngagementOrm, ContentItemViewOrm
from libs.database.session import create_db_session_factory


async def main() -> None:
    app_settings = AppSettings()
    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    blog_post_identity = UUID(os.environ["BLOG_POST_IDENTITY"])
    async with db_session_factory() as db_session:
        content_item_id_query = select(BlogPostOrm.content_item_id).where(
            BlogPostOrm.identity == blog_post_identity
        )
        content_item_id = await db_session.scalar(content_item_id_query)
        engagement_query = select(ContentItemEngagementOrm).where(
            ContentItemEngagementOrm.content_item_id == content_item_id
        )
        engagement_record = await db_session.scalar(engagement_query)
        view_row_count_query = select(func.count()).where(
            ContentItemViewOrm.content_item_id == content_item_id
        )
        view_row_count = await db_session.scalar(view_row_count_query)
        anonymous_view_row_count_query = view_row_count_query.where(
            ContentItemViewOrm.anonymous_user_key.is_not(None)
        )
        anonymous_view_row_count = await db_session.scalar(anonymous_view_row_count_query)
    await db_engine.dispose()
    if engagement_record is None:
        raise SystemExit("the post has no engagement row")
    print(
        engagement_record.view_count,
        engagement_record.read_percent_sum,
        engagement_record.feed_score,
        view_row_count,
        anonymous_view_row_count,
    )


asyncio.run(main())
PY
}

# Fails unless the post's engagement is $2 views and a read sum of $3, across $4 view
# rows of which $5 are signed out. Prints the score for comparison.
expect_engagement() {
  local blog_post_identity="$1" view_count read_percent_sum feed_score view_rows anonymous_view_rows
  read -r view_count read_percent_sum feed_score view_rows anonymous_view_rows \
    <<<"$(read_engagement "$blog_post_identity")"
  printf '  views %s, read sum %s, score %s, view rows %s (%s signed out)\n' \
    "$view_count" "$read_percent_sum" "$feed_score" "$view_rows" "$anonymous_view_rows" >&2
  [ "$view_count" = "$2" ] || fail "view_count: expected $2, got $view_count"
  [ "$read_percent_sum" = "$3" ] || fail "read_percent_sum: expected $3, got $read_percent_sum"
  [ "$view_rows" = "$4" ] || fail "view rows: expected $4, got $view_rows"
  [ "$anonymous_view_rows" = "$5" ] || fail "signed-out view rows: expected $5, got $anonymous_view_rows"
  pass "engagement is $2 views, read sum $3"
  LAST_FEED_SCORE="$feed_score"
}

step "1. Create a public persona with a published public post and a private post"
PERSONA_BODY="$(request "$OWNER_SESSION" 201 "create persona" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@PERSONA_NAME bio=@PERSONA_BIO is_public=true)")"
PERSONA_IDENTITY="$(echo "$PERSONA_BODY" | read_json_field identity)"
export PERSONA_IDENTITY
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
# A view is recorded against the post's content item, which the post's response names
PUBLIC_CONTENT_ITEM_IDENTITY="$(request "$OWNER_SESSION" 200 "fetch public post" \
  "$API_URL/blog-posts/$PUBLIC_POST_IDENTITY" | read_json_field content_item_identity)"
PRIVATE_CONTENT_ITEM_IDENTITY="$(request "$OWNER_SESSION" 200 "fetch private post" \
  "$API_URL/blog-posts/$PRIVATE_POST_IDENTITY" | read_json_field content_item_identity)"

step "2. A new post has an engagement row and a score, with no views"
expect_engagement "$PUBLIC_POST_IDENTITY" 0 0 0 0
STARTING_FEED_SCORE="$LAST_FEED_SCORE"
[ "$STARTING_FEED_SCORE" != "None" ] || fail "a published post has no score"
pass "the published post starts with a score"

VIEW_URL="$API_URL/content-items/$PUBLIC_CONTENT_ITEM_IDENTITY/view"
view_body() { json_body read_percent="$1"; }

step "3. A signed-out reader opens the post — one view"
request_signed_out 200 "signed out opens it" -X PUT "$VIEW_URL" -A "$FIRST_BROWSER" \
  -H 'Content-Type: application/json' -d "$(view_body 0)" >/dev/null
expect_engagement "$PUBLIC_POST_IDENTITY" 1 0 1 1

step "4. They read to 50%, report it twice, then report 25% — only the first 50% counts"
request_signed_out 200 "signed out reaches 50%" -X PUT "$VIEW_URL" -A "$FIRST_BROWSER" \
  -H 'Content-Type: application/json' -d "$(view_body 50)" >/dev/null
request_signed_out 200 "signed out reports 50% again" -X PUT "$VIEW_URL" -A "$FIRST_BROWSER" \
  -H 'Content-Type: application/json' -d "$(view_body 50)" >/dev/null
request_signed_out 200 "signed out reports 25%" -X PUT "$VIEW_URL" -A "$FIRST_BROWSER" \
  -H 'Content-Type: application/json' -d "$(view_body 25)" >/dev/null
expect_engagement "$PUBLIC_POST_IDENTITY" 1 50 1 1

step "5. They finish it, then open it again — still one view, read sum 100"
request_signed_out 200 "signed out reaches 100%" -X PUT "$VIEW_URL" -A "$FIRST_BROWSER" \
  -H 'Content-Type: application/json' -d "$(view_body 100)" >/dev/null
request_signed_out 200 "signed out opens it again" -X PUT "$VIEW_URL" -A "$FIRST_BROWSER" \
  -H 'Content-Type: application/json' -d "$(view_body 0)" >/dev/null
expect_engagement "$PUBLIC_POST_IDENTITY" 1 100 1 1

step "6. A second browser is a second signed-out reader"
request_signed_out 200 "second browser opens it" -X PUT "$VIEW_URL" -A "$SECOND_BROWSER" \
  -H 'Content-Type: application/json' -d "$(view_body 0)" >/dev/null
expect_engagement "$PUBLIC_POST_IDENTITY" 2 100 2 2

step "7. A second signed-in user reads it all"
request "$OTHER_SESSION" 200 "second user opens it" -X PUT "$VIEW_URL" \
  -H 'Content-Type: application/json' -d "$(view_body 0)" >/dev/null
request "$OTHER_SESSION" 200 "second user reaches 100%" -X PUT "$VIEW_URL" \
  -H 'Content-Type: application/json' -d "$(view_body 100)" >/dev/null
expect_engagement "$PUBLIC_POST_IDENTITY" 3 200 3 2

step "8. The owner's own views aren't recorded"
request "$OWNER_SESSION" 200 "owner opens it" -X PUT "$VIEW_URL" \
  -H 'Content-Type: application/json' -d "$(view_body 100)" >/dev/null
expect_engagement "$PUBLIC_POST_IDENTITY" 3 200 3 2

step "9. The score rose with engagement"
python3 -c "import sys; sys.exit(0 if float('$LAST_FEED_SCORE') > float('$STARTING_FEED_SCORE') else 1)" \
  || fail "score didn't rise: $STARTING_FEED_SCORE → $LAST_FEED_SCORE"
pass "score $STARTING_FEED_SCORE → $LAST_FEED_SCORE"

step "10. What can't be recorded"
request_signed_out 422 "a read_percent that isn't a quarter" -X PUT "$VIEW_URL" \
  -H 'Content-Type: application/json' -d "$(view_body 30)" >/dev/null
request_signed_out 404 "signed out views the private post" \
  -X PUT "$API_URL/content-items/$PRIVATE_CONTENT_ITEM_IDENTITY/view" \
  -H 'Content-Type: application/json' -d "$(view_body 0)" >/dev/null
request "$OTHER_SESSION" 404 "second user views the private post" \
  -X PUT "$API_URL/content-items/$PRIVATE_CONTENT_ITEM_IDENTITY/view" \
  -H 'Content-Type: application/json' -d "$(view_body 0)" >/dev/null
EXPIRED_STATUS="$(curl -s -o /dev/null -w '%{http_code}' -b "sid=not-a-real-session" -X PUT "$VIEW_URL" \
  -H 'Content-Type: application/json' -d "$(view_body 0)")"
[ "$EXPIRED_STATUS" = "401" ] || fail "an expired session: expected 401, got $EXPIRED_STATUS"
pass "expired session → 401"
expect_engagement "$PUBLIC_POST_IDENTITY" 3 200 3 2

printf '\n\033[32mAll steps passed.\033[0m\n'
