# Persona Blog — build plan

Alpha target: a user can sign in, hit a writing endpoint, and get real LLM output
back. Personas and saved posts come after this plan.

Every step is one branch, one PR, reviewed and merged to `main` before the next
starts. Branch names follow the Git section of `CLAUDE.md`:
`feat/setup-api-skeleton`. Steps 1–3 are the exception and land
directly on `main`.

## Settled decisions

| Decision | Choice |
|----------|--------|
| Session strategy | Server-side session in Redis, session id in an httpOnly cookie |
| Redis | In from the start, for sessions |
| `/ai-write` persistence in step 6 | None. Request → LLM → response, nothing stored |
| First OpenAI model | `gpt-4o-mini`, overridable in TOML |
| Frontend styling | Tailwind, set up in step 4 |

## Naming settled for this plan

- Python packages snake_case, URL paths kebab-case: `libs/ai_write/`,
  `apps/api/domains/ai_write/`, router prefix `/ai-write`.
- `character_count`, not `char_length`.
- The step-6 result is `GenerateWritingResult`.

---

## Step 1 — `.claude/` config

Manual, by Tyler.

```
persona-blog/
├── CLAUDE.md                        # repo root, NOT inside .claude/
└── .claude/
    ├── rules/
    │   ├── python-naming.md
    │   └── fastapi-structure.md
    ├── commands/
    │   └── add-domain.md
    └── skills/
        └── db-migration/
            ├── SKILL.md
            └── reference/migration_runner.py
```

**Verify:** open Claude Code in the folder, type `/` and confirm `add-domain`
appears. Ask "what are the naming rules for this project" and confirm it answers
from the rules file rather than generically.

---

## Step 2 — Subagents

Manual, by Tyler. Do this before any code exists so the agents are available from
step 3 onward.

### 1. Ask Claude to create it

In Claude Code:

```
Create a fastapi-coder subagent in this project's .claude/agents/ that writes
backend files following an already-decided pattern: DTOs, Input and Result
models, dependency factories, thin routers, and Orm classes. Its system prompt
must instruct it to read .claude/rules/python-naming.md and
.claude/rules/fastapi-structure.md before writing anything, and to report which
conventions it applied. Give it Read, Write, Edit, Glob, and Grep. Use Sonnet.
```

Then the second one:

```
Create a test-writer subagent in this project's .claude/agents/ that writes
pytest coverage for existing services and routes, including fixtures and stubs.
It must read .claude/rules/pytest-testing.md, .claude/rules/python-naming.md and
.claude/rules/fastapi-structure.md first, and must not modify files outside
backend/tests/. Give it Read, Write, Edit, Glob, Grep, and Bash, with its system
prompt limiting Bash to pytest and ruff on tests/. Use Sonnet.
```

### 2. Review the files

Open `.claude/agents/fastapi-coder.md` and confirm the frontmatter and system
prompt. It should look close to:

```markdown
---
name: fastapi-coder
description: Writes backend files that follow an established pattern — DTOs, Input and Result models, dependency factories, thin routers, Orm classes. Use when the design is decided and the work is filling in a known shape. Not for design decisions or business logic.
tools: Read, Write, Edit, Glob, Grep
model: sonnet
---

Before writing any file, read .claude/rules/python-naming.md and
.claude/rules/fastapi-structure.md in full. Those rules govern every name and
every file location; where they conflict with your defaults, they win.

You write code for a pattern that is already decided. You do not choose
architecture, invent conventions, or add business logic that was not specified.

If the task requires a convention the rules files do not cover, stop and report
what is missing instead of picking one.

When you finish, report: files created or changed, the conventions you applied,
and anything you were unsure about.
```

The body below the frontmatter **is** the system prompt — that is where the
pointer to the rules files lives. Subagents run in their own context and do not
reliably inherit `CLAUDE.md` or the path-scoped rules, so without those first two
lines you get plausible code using `session` instead of `db_session` and
`UserResult` instead of `GetUserByEmailResult`.

Because these live in the project's `.claude/agents/`, they're scoped to this repo
and get committed with it. `~/.claude/agents/` would make them available in every
project on the machine; project scope wins on a name collision.

### 3. Try it out

```
Use the fastapi-coder agent to list what it would create for a trivial "ping"
domain, without writing anything yet.
```

The delegation shows in the transcript as a tool call row —
`fastapi-coder(...)`. If Claude can't find the agent, restart Claude Code: a
running session doesn't detect a newly created `agents` directory.

### On running several at once

Don't create `fastapi-coder-1` and `fastapi-coder-2`. One definition can be
dispatched multiple times in parallel — the main agent launches several instances
of the same subagent with different tasks, each in its own context. Numbered
duplicates give you no extra parallelism and two files that drift apart.

Parallelism helps when the tasks are genuinely independent and touch different
files (three domains scaffolded at once). It hurts when they touch the same file,
since they can't see each other's edits. Split work by file, not by step.

### Later

If the agents need instructions beyond the shared rules, add
`.claude/rules/subagent-conventions.md` and point their system prompts at it too,
rather than growing each agent's prompt separately.

---

## Step 3 — Repo, git, CI

`gh` can create the remote, but **run `gh auth login` yourself first** — it's
interactive and the agent can't complete it.

```bash
gh repo create persona-blog --private --source=. --remote=origin --push
```

This step commits directly to `main`. Everything after it is a branch.

Build:
- `git init`, rename `master` → `main` (`git branch -m main`)
- `.gitignore` — Python, Node, `.env`, `CLAUDE.local.md`, `config.local.toml`
- `README.md` — one paragraph and the run commands

CI is deferred to step 5: before `backend/pyproject.toml` exists `uv sync` has
nothing to install, and `pytest` exits 5 when it collects no tests, so the workflow
would be red from the first push.

**Verify:** `git log` shows the commits on `main`; `gh repo view --web` opens the
right repo.

---

## Step 4 — Frontend placeholder

React + Vite in `frontend/`, TypeScript, no API calls, no router.

```bash
npm create vite@latest frontend -- --template react-ts
```

Strip the boilerplate to a single page rendering the app name. Add Tailwind now
rather than retrofitting it over existing markup. `frontend/README.md` with the dev
command.

**Verify:** `npm run dev` loads with no console errors, a Tailwind utility class
visibly applies, `npm run build` succeeds.

---

## Step 5 — API skeleton + health domain

No database, no libs beyond what the app needs.

Build:
- `backend/pyproject.toml` via `uv init`, plus `uv lock`
- Ruff and pytest config in `pyproject.toml`
- `apps/api/core/config.py` — `AppSettings` with `app_name: str = "Persona Blog API"`
  and `environment: EnvironmentType` (`DEVELOPMENT` / `TEST` / `PRODUCTION`, in
  `apps/api/core/types.py`), loading `config.toml` and env
- `config.toml` carrying only `environment = "DEVELOPMENT"` — TOML holds only what
  differs between environments. `tests/api/core/test_config.py` proves TOML beats
  the default and env beats TOML
- `apps/api/core/dtos.py` — the shared CRUD response DTOs: `IdentityResponseDto
  { identity: str }` for creates, `EmptyResponseDto {}` for updates and deletes.
  Nothing uses them until the first CRUD domain, but `fastapi-coder` treats this as
  a setup file and won't create it
- `apps/api/lifespan.py` — logs `api_started` with `app_name` and `environment` from
  settings, closes cleanly
- `apps/api/core/exception_handlers.py` — the standard exception → status code map
  and `register_exception_handlers()`
- `apps/api/app_factory.py` — `create_app()`, registers exception handlers, includes
  routers
- `apps/api/main.py` — `app = create_app()`
- structlog with a console renderer for dev; Logfire deferred to step 13
- `apps/api/domains/health/` — `router.py`, `dtos.py` with
  `HealthResponseDto { status, app_name, environment }`. No lib: health has no
  business logic and is the one domain allowed to skip `libs/`
- `tests/api/health/test_router.py` using `httpx.AsyncClient` with
  `ASGITransport`, plus `tests/api/core/test_config.py` and
  `tests/api/core/test_exception_handlers.py`. `test_lifespan.py` waits for step 8, when the
  lifespan first owns a resource
- `.github/workflows/ci.yml` — on push and PR, from `backend/`:
  `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest`. Deferred from
  step 3; the health test is what gives `pytest` something to collect

**Verify:**
```bash
uv run granian --interface asgi apps.api.main:app --reload
curl localhost:8000/health
uv run pytest
```
The Actions run on the PR is green.
Add `app_name = "..."` to `config.toml`, restart, confirm the log and `/health` both
change (remove it afterwards). Then set `APP_NAME=...` as an env var and confirm it beats the TOML value.

**Watch for:** this is where the granian invocation and module path in `CLAUDE.md`
get corrected to whatever actually works.

---

## Step 6 — `ai_write` skeleton, app ↔ lib wired

No LLM yet. This step proves the layering end to end.

Build:
- `libs/ai_write/` — `services.py` with `AiWriteService.generate_writing()`,
  `inputs.py` with `GenerateWritingInput { writing_type, prompt_text }`,
  `results.py` with `GenerateWritingResult { content, character_count }`
- `WritingType(StrEnum)` with the single member `BLOG_POST = "BLOG_POST"` in
  `libs/ai_write/types.py`
- The service returns a hardcoded string and the real `len()` of it
- `apps/api/domains/ai_write/` — `dtos.py` with `GenerateWritingDto` + `to_input()`
  and `WritingResponseDto` + `from_result()`, `dependencies.py`, `router.py` at
  `/ai-write`
- Tests both sides: service called directly, route via the test client

**Verify:**
```bash
curl -X POST localhost:8000/ai-write \
  -H 'content-type: application/json' \
  -d '{"writing_type":"BLOG_POST","prompt_text":"a post about sourdough"}'
```
Returns the fake content and a correct `character_count`. Post an invalid
`writing_type` and confirm a readable 422. Confirm `grep -r "from apps" libs/`
returns nothing.

---

## Step 7 — LLM lib, real output

Build:
- `libs/llm/` — `services.py` with `LlmService.complete()`, `settings.py` with
  `LlmSettings { model_name, request_timeout_seconds, max_output_tokens }`,
  `inputs.py`, `results.py` with
  `LlmCompletionResult { content, input_tokens, output_tokens }`
- OpenAI only. One provider, no abstraction layer — add `LlmProviderType(StrEnum)`
  when a second provider actually arrives
- API key from env via `AppSettings`, never TOML
- `libs/ai_write/prompts.py` — `AiWritePrompt.build_system_prompt()` and
  `.build_user_prompt(prompt_text, writing_type)`, templates as `UPPER_SNAKE`
  constants
- `AiWriteService` takes an `LlmService` through `__init__`; the dependency factory
  wires it
- Log token counts per call at info level
- Tests use a stub `LlmService`, never the real API

**Verify:** same curl as step 6, now real generated text. Remove the API key and
confirm a clean error response rather than a stack trace. Confirm the log line shows
token counts. `uv run pytest` passes with no network.

---

## Step 8 — Postgres + Redis via docker compose

Build:
- `docker-compose.yml` — Postgres 18 and Redis 8, named volumes, healthchecks
- `.env.example` with `DATABASE_URL`, `REDIS_URL`, and the OpenAI key name
- `libs/database/base.py`, `session.py` (async engine + `async_sessionmaker`),
  empty `orm/__init__.py`
- Redis client created in `lifespan`, stored on `app.state`, closed on shutdown
- `get_db_session` and `get_db_transaction` in `apps/api/core/dependencies.py`
- `/health` extended to check both Postgres (`SELECT 1`) and Redis (`PING`)

**Verify:** `docker compose up -d`, `/health` reports both as reachable. Stop each
container in turn and confirm `/health` degrades without the app crashing.

---

## Step 9 — Migration system + users table

Uses the `db-migration` skill.

Build:
- `migrations/env.py` (no `target_metadata`), `alembic.ini` with `file_template` and
  `version_locations`, `migrations/migration_runner.py`
- `uv add sqlparse alembic`
- First revision: `users` — `id`, `email` (unique), `display_name`,
  `google_subject_id`, `created_at`, `updated_at`
- `libs/database/orm/user.py` with `UserOrm`, exported from `orm/__init__.py`
- CI job: apply migrations to an empty database, then the drift check against Orm
  metadata

**Verify:** `alembic upgrade head` on a fresh database, inspect with `psql \d users`.
`alembic downgrade -1`, confirm the table is gone, upgrade again. Rename a column in
the Orm class deliberately and confirm CI's drift check fails.

---

## Step 10 — Users lib and domain

Build:
- `libs/users/` — `services.py` with `get_user_by_email`, `create_user`,
  `get_or_create_from_google`; `inputs.py`; `results.py`
- `apps/api/domains/users/` — `dtos.py`, `dependencies.py`, `router.py` with
  `GET /users/me` (401 until step 11)
- Tests against a real test database, transaction rolled back per test

**Verify:** create a user through the service in a test and confirm the row lands.
Confirm a duplicate email raises the domain exception and maps to a 409.

---

## Step 11 — Google sign-in

Needs a Google Cloud OAuth client — **manual setup by Tyler**, redirect URI
`http://localhost:8000/auth/google/callback`.

Build:
- `libs/auth/` — Google token verification, session creation and validation against
  Redis. Session key holds the user id with a TTL; no sessions table
- `apps/api/domains/auth/` — `GET /auth/google/login`,
  `GET /auth/google/callback`, `POST /auth/logout`
- `CurrentUserDep` in `apps/api/core/dependencies.py` — the guard. Routes needing
  auth take it; that's the Passport-equivalent
- `/users/me` and `/ai-write` now require it

**Verify:** full browser round trip to a logged-in state. Cookie is httpOnly, and
`secure` is off only in dev. Call `/ai-write` without the cookie and get a 401. Log
out, then confirm the Redis key is actually gone (`redis-cli KEYS 'session:*'`), not
just the cookie cleared.

---

## Step 12 — Frontend auth + write screen

Build:
- Sign-in button hitting the backend login route
- A logged-in view showing `display_name` from `/users/me`
- A form posting to `/ai-write` and rendering the result
- Vite dev proxy to the API so cookies are same-origin
- A typed API client module; no `fetch` calls scattered through components

**Verify:** sign in, generate text, sign out, confirm the write form 401s. Hard
refresh mid-session and confirm you stay signed in.

---

## Step 13 — Alpha limits + Logfire

Build:
- Per-user generation cap (3), Tyler's account exempt. Counter in Redis
- structlog → Logfire wiring, request-id middleware
- Railway deploy config

**Verify:** hit the cap on a test account and confirm a clear 429 with a useful
message. Confirm traces appear in Logfire.

---

## Deliberately deferred

Personas, saved posts and the blog feed, the human-in-the-loop review flow, the
un-AI-ify module, LangGraph, Anthropic as a second provider, scheduled publishing,
RSS context. Step 13 ends with a working single-user writing tool, which is the
point at which the persona model can be designed against something real.
