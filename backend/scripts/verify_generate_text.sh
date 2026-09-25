#!/usr/bin/env bash
# Walks a blog post generation end to end against a running dev server and a real LLM:
# outline, draft and humanize, with the draft held for review. Prints each step, the run
# and step rows it wrote, and the LLM calls they cost. Run from backend/:
#
#   ./scripts/verify_generate_text.sh
#
# It signs in by minting a session for the first non-system user, so no browser needed.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
PROMPT_TEXT="${PROMPT_TEXT:-Why sourdough starter needs a feeding schedule}"
FEEDBACK_TEXT="${FEEDBACK_TEXT:-Too general. Give concrete timings and temperatures.}"
# Exported so the json_body python below can read them from os.environ.
PERSONA_INFO="${PERSONA_INFO:-Writes plainly, bakes at home, distrusts jargon.}"
export PROMPT_TEXT FEEDBACK_TEXT PERSONA_INFO

step() { printf '\n\033[1m── %s\033[0m\n' "$1"; }
fail() { printf '\033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
pass() { printf '\033[32m  ok\033[0m %s\n' "$1"; }

read_json_field() { python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
# Builds a JSON object from key=value pairs: @NAME reads environment variable NAME as
# a string, anything else is parsed as a JSON literal. The python is single-quoted and
# the pairs arrive as argv because bash 3.2, still Apple's /bin/bash, mis-parses a
# double-quoted $( ) that contains double quotes: the braces end up unquoted and the
# payload is brace-expanded into two arguments.
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

step "Checking the dev server"
if ! curl -sf --max-time 3 "$API_URL/health" >/dev/null; then
  fail "no server at $API_URL — start it with: uv run granian --interface asgi apps.api.main:app --reload"
fi
pass "$API_URL is up"

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

step "1. Generate a blog post — outline auto-approved, draft held for review"
GENERATE_RESPONSE="$(curl -sf -X POST "$API_URL/generate-text/blog-post" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d "$(json_body prompt_text=@PROMPT_TEXT persona_info=@PERSONA_INFO \
        additional_context=null \
        options='{"outline": {"is_enabled": true, "is_auto_approved": true}, "draft": {"is_auto_approved": false}, "humanize": {"is_enabled": true, "is_auto_approved": true}}')")"
echo "$GENERATE_RESPONSE" | print_json
RUN_IDENTITY="$(echo "$GENERATE_RESPONSE" | read_json_field run_identity)"
[ "$(echo "$GENERATE_RESPONSE" | read_json_field status)" = "AWAITING_REVIEW" ] || fail "expected AWAITING_REVIEW"
pass "run $RUN_IDENTITY paused at $(echo "$GENERATE_RESPONSE" | read_json_field current_step)"

step "2. Read the run back"
curl -sf -b "sid=$SESSION_ID" "$API_URL/generate-text/runs/$RUN_IDENTITY" | print_json
pass "the run reports its own cost and token counts"

step "3. Reject the draft with direction — expect a rewrite, paused again"
REJECT_RESPONSE="$(curl -sf -X POST "$API_URL/generate-text/runs/$RUN_IDENTITY/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d "$(json_body is_approved=false feedback_text=@FEEDBACK_TEXT)")"
echo "$REJECT_RESPONSE" | print_json
[ "$(echo "$REJECT_RESPONSE" | read_json_field status)" = "AWAITING_REVIEW" ] || fail "expected AWAITING_REVIEW"
[ "$(echo "$REJECT_RESPONSE" | read_json_field content)" != "$(echo "$GENERATE_RESPONSE" | read_json_field content)" ] \
  || fail "the rewrite returned the same draft"
pass "the draft changed after feedback"

step "4. Approve — the run finishes through humanize"
APPROVE_RESPONSE="$(curl -sf -X POST "$API_URL/generate-text/runs/$RUN_IDENTITY/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d "$(json_body is_approved=true feedback_text=null)")"
echo "$APPROVE_RESPONSE" | print_json
[ "$(echo "$APPROVE_RESPONSE" | read_json_field status)" = "COMPLETED" ] || fail "expected COMPLETED"
pass "run completed"

check_status() {
  local expected="$1" description="$2" actual
  shift 2
  actual="$(curl -s -o /dev/null -w '%{http_code}' "$@")"
  [ "$actual" = "$expected" ] || fail "$description: expected $expected, got $actual"
  pass "$description → $expected"
}

step "5. The error paths"
check_status 409 "resuming a finished run" \
  -X POST "$API_URL/generate-text/runs/$RUN_IDENTITY/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d '{"is_approved": true, "feedback_text": null}'
check_status 404 "reading a run that never existed" \
  -b "sid=$SESSION_ID" "$API_URL/generate-text/runs/00000000-0000-0000-0000-000000000000"
check_status 422 "a malformed run identity" \
  -b "sid=$SESSION_ID" "$API_URL/generate-text/runs/not-a-uuid"
check_status 401 "generating while signed out" \
  -X POST "$API_URL/generate-text/blog-post" \
  -H 'Content-Type: application/json' \
  -d '{"prompt_text": "anything", "persona_info": null, "additional_context": null, "options": {"draft": {"is_auto_approved": true}}}'

step "6. What the run recorded"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT status, current_step, graph_version, llm_call_count, input_tokens, output_tokens, cost_usd
   FROM pb_generate_text_run WHERE identity = '$RUN_IDENTITY';"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT s.step_number, s.step_name, s.attempt, s.status, s.human_decision, s.llm_call_count, s.cost_usd, s.duration_ms
   FROM pb_generate_text_step s
   JOIN pb_generate_text_run r ON r.id = s.run_id
   WHERE r.identity = '$RUN_IDENTITY' ORDER BY s.step_number;"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT c.purpose, c.model_name, c.status, c.input_tokens, c.output_tokens, c.cost_usd, s.step_name
   FROM pb_llm_call c
   JOIN pb_generate_text_run r ON r.id = c.run_id
   LEFT JOIN pb_generate_text_step s ON s.id = c.step_id
   WHERE r.identity = '$RUN_IDENTITY' ORDER BY c.created_at;"

printf '\n\033[32mAll steps passed.\033[0m One step row per node, and every LLM call tied to its step.\n'
