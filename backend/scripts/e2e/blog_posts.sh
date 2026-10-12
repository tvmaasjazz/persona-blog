#!/usr/bin/env bash
# Walks the Markdown blog post output and blog post CRUD end to end against a running dev
# server and a real LLM: generates a post as a persona, saves the run as a blog post,
# writes one by hand, publishes, schedules and deletes, and checks what a second user can
# see. Prints each response, checks what it can, and shows the rows it wrote. Run from
# backend/:
#
#   ./scripts/e2e/blog_posts.sh
#
# It signs in as the first non-system user, and as a dedicated second user
# (verify-second-user@persona-blog.invalid) that it creates in the local database the
# first time it runs. Names carry a timestamp, so it can run again.
# The LLM calls are real and billed to the OPENAI_API_KEY in .env. It refuses to run
# unless .env points at a local development database.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
EXPECTED_GRAPH_VERSION="2026-10-07.2"
RUN_SUFFIX="$(date +%H%M%S)"
# Exported so the json_body python below can read them from os.environ.
PUBLIC_PERSONA_NAME="Marta Quill $RUN_SUFFIX"
PRIVATE_PERSONA_NAME="Dev Ashford $RUN_SUFFIX"
PERSONA_BIO="Home baker who writes plainly about bread and the science under it."
PROMPT_TEXT="Why a sourdough starter needs a feeding schedule"
TONE="warm, practical"
TARGET_AUDIENCE="home bakers"
MANUAL_TITLE="Notes From a Slow Morning $RUN_SUFFIX"
MANUAL_SUBTITLE="What the oven taught me this week"
MANUAL_BODY="A paragraph to open the post.

## What Changed

The dough rose slower than I expected."
H1_BODY="# A Title Inside the Body

Not allowed."
NOW_ISO="$(python3 -c 'from datetime import UTC, datetime; print(datetime.now(UTC).isoformat())')"
FUTURE_ISO="$(python3 -c 'from datetime import UTC, datetime, timedelta; print((datetime.now(UTC) + timedelta(days=30)).isoformat())')"
export PUBLIC_PERSONA_NAME PRIVATE_PERSONA_NAME PERSONA_BIO PROMPT_TEXT TONE TARGET_AUDIENCE \
  MANUAL_TITLE MANUAL_SUBTITLE MANUAL_BODY H1_BODY NOW_ISO FUTURE_ISO

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
from libs.auth.services import AuthSessionService
from libs.database.orm import UserOrm
from libs.database.session import create_db_session_factory

SECOND_USER_EMAIL = "verify-second-user@persona-blog.invalid"


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
            second_user_record = UserOrm(email=SECOND_USER_EMAIL, display_name="Verify Second User")
            db_session.add(second_user_record)
            await db_session.flush()

    redis_client = Redis.from_url(app_settings.redis_url)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    for user_record in (first_user_record, second_user_record):
        session_id = await auth_session_service.create_session(user_record.id, user_record.identity)
        print(session_id)
    await redis_client.aclose()
    await db_engine.dispose()


asyncio.run(main())
PY
)"
OWNER_SESSION="$(echo "$SESSION_IDS" | sed -n 1p)"
OTHER_SESSION="$(echo "$SESSION_IDS" | sed -n 2p)"
pass "two sessions ready"

step "1. Create a public persona and a private one"
PUBLIC_PERSONA_BODY="$(request "$OWNER_SESSION" 201 "create public persona" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@PUBLIC_PERSONA_NAME bio=@PERSONA_BIO is_public=true)")"
PUBLIC_PERSONA_IDENTITY="$(echo "$PUBLIC_PERSONA_BODY" | read_json_field identity)"
PRIVATE_PERSONA_BODY="$(request "$OWNER_SESSION" 201 "create private persona" -X POST "$API_URL/personas" \
  -H 'Content-Type: application/json' \
  -d "$(json_body name=@PRIVATE_PERSONA_NAME bio=@PERSONA_BIO is_public=false)")"
PRIVATE_PERSONA_IDENTITY="$(echo "$PRIVATE_PERSONA_BODY" | read_json_field identity)"
export PUBLIC_PERSONA_IDENTITY PRIVATE_PERSONA_IDENTITY

step "2. Generate a blog post as the public persona (real LLM calls, every step auto-approved)"
GENERATE_BODY="$(request "$OWNER_SESSION" 200 "generate" -X POST "$API_URL/generate-text/blog-post" \
  -H 'Content-Type: application/json' \
  -d "$(json_body prompt_text=@PROMPT_TEXT persona_identity=@PUBLIC_PERSONA_IDENTITY \
        tone=@TONE target_audience=@TARGET_AUDIENCE additional_context=null \
        options='{"outline": {"is_enabled": true, "is_auto_approved": true}, "draft": {"is_auto_approved": true}, "humanize": {"is_enabled": true, "is_auto_approved": true}}')")"
RUN_IDENTITY="$(echo "$GENERATE_BODY" | read_json_field run_identity)"
[ "$(echo "$GENERATE_BODY" | read_json_field status)" = "COMPLETED" ] || fail "expected the run to be COMPLETED"
[ "$(echo "$GENERATE_BODY" | read_json_field graph_version)" = "$EXPECTED_GRAPH_VERSION" ] \
  || fail "expected graph_version $EXPECTED_GRAPH_VERSION"
GENERATED_CONTENT="$(echo "$GENERATE_BODY" | read_json_field content)"
case "$GENERATED_CONTENT" in "# "*) ;; *) fail "the post doesn't start with '# Title'" ;; esac
GENERATED_TITLE="$(echo "$GENERATED_CONTENT" | head -1 | sed 's/^# //')"
export RUN_IDENTITY
pass "run $RUN_IDENTITY completed as Markdown titled '$GENERATED_TITLE'"

step "3. Save the run as a blog post — the server splits title, subtitle and body"
SAVED_BODY="$(request "$OWNER_SESSION" 201 "save run as post" -X POST "$API_URL/blog-posts/from-generate-text-run" \
  -H 'Content-Type: application/json' \
  -d "$(json_body generate_text_run_identity=@RUN_IDENTITY)")"
SAVED_POST_IDENTITY="$(echo "$SAVED_BODY" | read_json_field identity)"
SAVED_POST="$(request "$OWNER_SESSION" 200 "read the saved post" "$API_URL/blog-posts/$SAVED_POST_IDENTITY")"
[ "$(echo "$SAVED_POST" | read_json_field title)" = "$GENERATED_TITLE" ] || fail "the title wasn't split out of the run"
[ "$(echo "$SAVED_POST" | read_json_field persona_identity)" = "$PUBLIC_PERSONA_IDENTITY" ] \
  || fail "the persona didn't come from the run"
if echo "$SAVED_POST" | read_json_field body | grep -q '^# '; then fail "the body still holds the title"; fi
pass "title split out, body has no H1, persona taken from the run"
pass "subtitle: $(echo "$SAVED_POST" | read_json_field subtitle)"

step "4. Saving the same run again is refused"
request "$OWNER_SESSION" 409 "save run twice" -X POST "$API_URL/blog-posts/from-generate-text-run" \
  -H 'Content-Type: application/json' \
  -d "$(json_body generate_text_run_identity=@RUN_IDENTITY)" >/dev/null

step "5. Write a post by hand"
MANUAL_BODY_RESPONSE="$(request "$OWNER_SESSION" 201 "create manual post" -X POST "$API_URL/blog-posts" \
  -H 'Content-Type: application/json' \
  -d "$(json_body persona_identity=@PUBLIC_PERSONA_IDENTITY title=@MANUAL_TITLE \
        subtitle=@MANUAL_SUBTITLE body=@MANUAL_BODY)")"
MANUAL_POST_IDENTITY="$(echo "$MANUAL_BODY_RESPONSE" | read_json_field identity)"

step "6. The checks on a hand-written post"
H1_RESPONSE="$(request "$OWNER_SESSION" 422 "H1 in the body" -X POST "$API_URL/blog-posts" \
  -H 'Content-Type: application/json' \
  -d "$(json_body persona_identity=@PUBLIC_PERSONA_IDENTITY title=@MANUAL_TITLE body=@H1_BODY)")"
[ "$(echo "$H1_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["detail"][0]["loc"])')" \
  = "['body', 'body']" ] || fail "the 422 doesn't point at the body field"
pass "the 422 points at the body field"
request "$OWNER_SESSION" 422 "public post on a private persona" -X POST "$API_URL/blog-posts" \
  -H 'Content-Type: application/json' \
  -d "$(json_body persona_identity=@PRIVATE_PERSONA_IDENTITY title=@MANUAL_TITLE \
        body=@MANUAL_BODY is_public=true)" >/dev/null

step "7. List the persona's posts — newest first"
LIST_BODY="$(request "$OWNER_SESSION" 200 "list by persona" "$API_URL/blog-posts?persona_identity=$PUBLIC_PERSONA_IDENTITY")"
LISTED_IDENTITIES="$(echo "$LIST_BODY" | python3 -c 'import json,sys; [print(p["identity"]) for p in json.load(sys.stdin)["blog_posts"]]')"
[ "$(echo "$LISTED_IDENTITIES" | sed -n 1p)" = "$MANUAL_POST_IDENTITY" ] || fail "expected the manual post first"
[ "$(echo "$LISTED_IDENTITIES" | sed -n 2p)" = "$SAVED_POST_IDENTITY" ] || fail "expected the saved post second"
pass "manual post, then the saved one"

update_manual_post() {
  local session_id="$1" expected="$2" description="$3" is_public="$4" published_at="$5"
  request "$session_id" "$expected" "$description" -X PUT "$API_URL/blog-posts/$MANUAL_POST_IDENTITY" \
    -H 'Content-Type: application/json' \
    -d "$(json_body title=@MANUAL_TITLE subtitle=@MANUAL_SUBTITLE body=@MANUAL_BODY \
          is_public="$is_public" published_at="$published_at")" >/dev/null
}

step "8. Publish now — the second user can read it but not change it"
update_manual_post "$OWNER_SESSION" 200 "publish now" true "\"$NOW_ISO\""
request "$OTHER_SESSION" 200 "second user reads it" "$API_URL/blog-posts/$MANUAL_POST_IDENTITY" >/dev/null
update_manual_post "$OTHER_SESSION" 403 "second user updates it" true "\"$NOW_ISO\""

step "9. Schedule for the future — hidden from the second user until then"
update_manual_post "$OWNER_SESSION" 200 "schedule in 30 days" true "\"$FUTURE_ISO\""
request "$OTHER_SESSION" 404 "second user reads a scheduled post" "$API_URL/blog-posts/$MANUAL_POST_IDENTITY" >/dev/null
request "$OWNER_SESSION" 200 "you still read it" "$API_URL/blog-posts/$MANUAL_POST_IDENTITY" >/dev/null

step "10. Unpublish — a draft again"
update_manual_post "$OWNER_SESSION" 200 "unpublish" true null
request "$OTHER_SESSION" 404 "second user reads a draft" "$API_URL/blog-posts/$MANUAL_POST_IDENTITY" >/dev/null

step "11. Delete the hand-written post"
request "$OWNER_SESSION" 200 "delete" -X DELETE "$API_URL/blog-posts/$MANUAL_POST_IDENTITY" >/dev/null
request "$OWNER_SESSION" 404 "read it after delete" "$API_URL/blog-posts/$MANUAL_POST_IDENTITY" >/dev/null

step "12. Signed out is refused"
SIGNED_OUT_STATUS="$(curl -s -o /dev/null -w '%{http_code}' "$API_URL/blog-posts")"
[ "$SIGNED_OUT_STATUS" = "401" ] || fail "listing while signed out: expected 401, got $SIGNED_OUT_STATUS"
pass "listing while signed out → 401"

step "13. What the database holds"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT b.identity AS blog_post, b.title, b.subtitle, left(b.body, 40) AS body_start,
          c.is_public, c.published_at, b.deleted_at IS NOT NULL AS b_deleted,
          c.deleted_at IS NOT NULL AS c_deleted
   FROM pb_blog_post b JOIN pb_content_item c ON c.id = b.content_item_id
   WHERE b.identity IN ('$SAVED_POST_IDENTITY', '$MANUAL_POST_IDENTITY') ORDER BY b.created_at;"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT r.identity AS run, r.status, r.graph_version, b.identity AS linked_blog_post
   FROM pb_generate_text_run r
   LEFT JOIN pb_content_item c ON c.id = r.content_item_id
   LEFT JOIN pb_blog_post b ON b.content_item_id = c.id
   WHERE r.identity = '$RUN_IDENTITY';"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT s.step_name, c.status,
          c.system_prompt LIKE '%single \`# Title\` line%' AS has_format_rules
   FROM pb_llm_call c
   JOIN pb_generate_text_run r ON r.id = c.run_id
   LEFT JOIN pb_generate_text_step s ON s.id = c.step_id
   WHERE r.identity = '$RUN_IDENTITY' ORDER BY c.created_at;"

printf '\n\033[32mAll steps passed.\033[0m The draft and humanize calls carry the format rules; the outline does not.\n'
