#!/usr/bin/env bash
# Walks the generate-text workflow end to end against a running dev server and a real
# LLM, printing each step and what came back. Run from backend/:
#
#   ./scripts/verify_generate_text.sh
#
# It signs in by minting a session for the first non-system user, so no browser needed.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
PROMPT_TEXT="${PROMPT_TEXT:-Why sourdough starter needs a feeding schedule}"
FEEDBACK_TEXT="${FEEDBACK_TEXT:-Too general. Give concrete timings and temperatures.}"

step() { printf '\n\033[1m── %s\033[0m\n' "$1"; }
fail() { printf '\033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
pass() { printf '\033[32m  ok\033[0m %s\n' "$1"; }

read_json_field() { python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }
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

step "1. Generate — expect AWAITING_REVIEW with a draft"
GENERATE_RESPONSE="$(curl -sf -X POST "$API_URL/generate-text/" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d "$(python3 -c "import json,os; print(json.dumps({'text_type': 'BLOG_POST', 'prompt_text': os.environ['PROMPT_TEXT']}))")")"
echo "$GENERATE_RESPONSE" | print_json
THREAD_IDENTITY="$(echo "$GENERATE_RESPONSE" | read_json_field thread_identity)"
[ "$(echo "$GENERATE_RESPONSE" | read_json_field status)" = "AWAITING_REVIEW" ] || fail "expected AWAITING_REVIEW"
pass "thread $THREAD_IDENTITY is awaiting review"

step "2. Reject with direction — expect a new draft, still AWAITING_REVIEW"
REJECT_RESPONSE="$(curl -sf -X POST "$API_URL/generate-text/$THREAD_IDENTITY/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d "$(python3 -c "import json,os; print(json.dumps({'is_approved': False, 'feedback_text': os.environ['FEEDBACK_TEXT']}))")")"
echo "$REJECT_RESPONSE" | print_json
[ "$(echo "$REJECT_RESPONSE" | read_json_field status)" = "AWAITING_REVIEW" ] || fail "expected AWAITING_REVIEW"
[ "$(echo "$REJECT_RESPONSE" | read_json_field content)" != "$(echo "$GENERATE_RESPONSE" | read_json_field content)" ] \
  || fail "the rewrite returned the same draft"
pass "the draft changed after feedback"

step "3. Approve — expect COMPLETED"
APPROVE_RESPONSE="$(curl -sf -X POST "$API_URL/generate-text/$THREAD_IDENTITY/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d '{"is_approved": true, "feedback_text": null}')"
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

step "4. The error paths"
check_status 409 "resuming a finished thread" \
  -X POST "$API_URL/generate-text/$THREAD_IDENTITY/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d '{"is_approved": true, "feedback_text": null}'
check_status 404 "resuming a thread that never existed" \
  -X POST "$API_URL/generate-text/00000000-0000-0000-0000-000000000000/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d '{"is_approved": true, "feedback_text": null}'
check_status 422 "a malformed thread identity" \
  -X POST "$API_URL/generate-text/not-a-uuid/resume" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d '{"is_approved": true, "feedback_text": null}'
check_status 401 "generating while signed out" \
  -X POST "$API_URL/generate-text/" \
  -H 'Content-Type: application/json' \
  -d '{"text_type": "BLOG_POST", "prompt_text": "anything"}'
check_status 422 "an unknown text type" \
  -X POST "$API_URL/generate-text/" \
  -H 'Content-Type: application/json' -b "sid=$SESSION_ID" \
  -d '{"text_type": "HAIKU", "prompt_text": "anything"}'

step "5. What the run recorded in pb_llm_call"
docker compose exec -T postgres psql -U pb -d pb_local -c \
  "SELECT purpose, llm_type, model_name, status, reason, input_tokens, output_tokens, cost_usd, duration_ms
   FROM pb_llm_call ORDER BY created_at DESC LIMIT 5;"

printf '\n\033[32mAll steps passed.\033[0m One row per generation and rewrite should appear above.\n'
