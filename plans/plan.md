# Persona Blog — build plan

Alpha target: a user can sign in, hit a writing endpoint, and get real LLM output
back. Personas and saved posts come after this plan.

Every step is one branch, one PR, reviewed and merged to `main` before the next
starts. Branch names follow the Git section of `CLAUDE.md`:
`feat/setup-api-skeleton`. Steps 1–3 are the exception and land
directly on `main`.

## Settled decisions

| Decision                          | Choice                                                         |
| --------------------------------- | -------------------------------------------------------------- |
| Session strategy                  | Server-side session in Redis, session id in an httpOnly cookie |
| Redis                             | In from the start, for sessions                                |
| `/generate-text` persistence      | No saved output. Only the LLM call log from step 12 is stored  |
| First OpenAI model                | `gpt-4o-mini`, overridable in TOML                             |
| Frontend styling                  | Tailwind, set up in step 4                                     |

## Naming settled for this plan

- Python packages snake_case, URL paths kebab-case: `libs/generate_text/`,
  `apps/api/domains/generate_text/`, router prefix `/generate-text`.
- Step 13 names are prefixed `GenerateText`: `GenerateTextService.generate_text()`,
  `GenerateTextInput`, `GenerateTextResult`, `GenerateTextDto`,
  `GeneratedTextResponseDto`, `GenerateTextPrompt`. The enum is `TextType`.
- `character_count`, not `char_length`.
- Every Postgres object is prefixed `pb_`: databases `pb_local` and `pb_test`, tables
  `pb_user`, enum types `pb_text_type`, and so on. Table names are singular. Alembic's
  `alembic_version` table keeps its default name.

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
- structlog with a console renderer for dev; Logfire deferred to step 14
- `apps/api/domains/health/` — `router.py`, `dtos.py` with
  `HealthResponseDto { status, app_name, environment }`. No lib: health has no
  business logic and is the one domain allowed to skip `libs/`
- `tests/api/health/test_router.py` using `httpx.AsyncClient` with
  `ASGITransport`, plus `tests/api/core/test_config.py` and
  `tests/api/core/test_exception_handlers.py`. `test_lifespan.py` waits for step 6, when the
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

## Step 6 — Postgres + Redis via docker compose

Build:

- `backend/docker-compose.yml` — Postgres 18 on host port 5437 and Redis 8 on host
  port 6387 (kept off the defaults so this doesn't clash with other local projects),
  named volumes, healthchecks. Database `pb_local`
- `backend/docker/postgres/init/` — creates `pb_test` beside `pb_local` when the
  volume is first created
- `backend/.env.example` with `DATABASE_URL` and `REDIS_URL`; `AppSettings` loads
  `.env`. The OpenAI key name joins it in step 12, since `AppSettings` rejects
  undeclared `.env` keys
- SQLAlchemy async engine and Redis client created in `lifespan`, stored on
  `app.state`, closed on shutdown. `tests/api/test_lifespan.py` covers both
- `/health` stays a liveness check — process up, nothing else. It does not check
  Postgres or Redis, so a backing-service blip never fails a deploy or restarts the
  API. A separate readiness endpoint can come later if deployment needs one
- CI gets Postgres and Redis service containers on the same ports as compose

**Verify:** `docker compose up -d --wait` reports both containers healthy, and
`pb_local` and `pb_test` both exist. The dev server starts with `.env` in place;
`uv run pytest` passes with compose up, and CI is green.

---

## Step 7 — Migration system + user tables

Uses the `db-migration` skill. The schema is designed in
[`user-tables.md`](user-tables.md): tables, shared columns, constraints, and the
system user.

Build:

- `uv add alembic sqlparse python-dotenv`
- `alembic.ini` with `file_template`, `version_locations` pointing at
  `migrations/revisions/`, and `prepend_sys_path = migrations` (commented) so
  revisions import `from migration_runner import MigrationRunner`
- `migrations/env.py` — async template with asyncpg, no `target_metadata`, no app
  imports. Loads `.env` with python-dotenv and reads `DATABASE_URL`.
  `transaction_per_migration=True`
- `migrations/migration_runner.py` — the reference runner from the `db-migration`
  skill, executing through `op.get_bind().exec_driver_sql()` instead of `op.execute()`,
  so a `:word` inside SQL isn't parsed as a bind parameter
- Ruff ignores N999 in `migrations/revisions/` (filenames start with digits)
- `libs/database/base.py` — `BaseOrm` with a constraint naming convention matching
  Postgres's defaults and the shared columns from `user-tables.md`: `id`, `identity`,
  timestamps, soft delete, audit foreign keys. `deleted_at` sits on `SoftDeleteMixin`,
  which `BaseOrm` inherits, because the soft-delete rule needs an unmapped class to
  target. `UtcDateTime` in `column_types.py` stores naive UTC and returns aware UTC
- `libs/database/session.py` — `create_db_session_factory(db_engine)` with
  `expire_on_commit=False`, plus the global soft-delete rule adding
  `deleted_at IS NULL` to every ORM query
- `libs/database/orm/` — `UserOrm` and `UserAuthProviderOrm`, exported from
  `__init__.py`. `AuthProviderType` in `libs/auth/types.py`
- `lifespan` stores `db_session_factory` on `app.state`
- `get_db_session` / `DbSessionDep` and `get_db_transaction` / `DbTransactionDep` in
  `apps/api/core/dependencies.py`
- Revision 1 `enable_citext`: `extensions/0001_enable_citext`
- Revision 2 `create_user_tables`: `pb_user/0001_create_pb_user`,
  `pb_user_auth_provider/0001_create_pb_user_auth_provider`
- Revision 3 `insert_system_user`: `pb_user/0002_insert_system_user`
- `scripts/check_schema_drift.py` — compares a database already at head with
  `BaseOrm.metadata` (ignoring `alembic_version`) and exits non-zero on any difference.
  Run with `uv run python -m scripts.check_schema_drift`
- Tests:
  - root `db_engine`, `db_connection`, `db_session_factory` and `db_session` fixtures;
    `fastapi_app` points at the test session factory
  - `tests/factories/users.py` with `insert_user_row`
  - `tests/api/core/test_dependencies.py`
  - `BaseOrm` behaviour: `updated_at` set on update, UTC round trip, soft-deleted rows
    hidden
  - `tests/migrations/`: single head, every up file has a down file, and the stairway
    test marked `migration`
- CI: the existing job runs migrations through the fixtures. A new `migrations` job
  runs `alembic upgrade head`, the drift check, and `pytest -m migration`
- Rules updated for the new conventions: shared columns on `BaseOrm`, `identity` in routes
  and DTOs, naive UTC timestamps, no triggers, `is_` booleans, `sql/extensions/`, the
  string foreign key exception for the audit columns, global soft delete, `AuthUser`
  passed to services, and the `MigrationRunner` example matching the skill

**Verify:** `alembic upgrade head` on a fresh database, inspect with `psql \d pb_user`
and `\d pb_user_auth_provider`, and confirm the system user row. `alembic downgrade
base`, confirm both tables and `citext` are gone, upgrade again. Rename a column in an
Orm class deliberately and confirm the drift check fails.

---

## Step 8 — Users lib

Lib only. There is no create-user route or `create_user` method: Google sign-in is the
only way an account is created, and tests insert users with factories. `GET /users/me`
lands in step 9, once `AuthUserDep` exists to guard it.

Build:

- `libs/users/services.py` — `UserService`, taking a db session:
  - `find_or_create_user_from_auth_provider(find_or_create_user_from_auth_provider_input)`,
    the sign-in path. The input carries what the provider returns: `provider`,
    `provider_subject`, `email`, `is_email_verified`, `display_name`, `avatar_url`.
    1. Finds the `pb_user_auth_provider` row by `(provider, provider_subject)`, then its
       user. A user that is inactive, or soft-deleted while its provider row isn't,
       raises `ForbiddenException` (403)
    2. Otherwise, if a live user already has the email, raises `ConflictException`
       (409). No linking by email while Google is the only provider
    3. Otherwise creates the `pb_user` row, flushes for its `id`, and creates the
       `pb_user_auth_provider` row with that `id` as `created_by_id` and
       `updated_by_id`
    - Returns the user's `id` and `identity`, what step 9's `AuthUser` needs
  - `find_user_by_identity(user_identity)` — raises `NotFoundException` (404) when
    missing
- `libs/users/inputs.py`, `libs/users/results.py`
- `tests/factories/users.py` gains `insert_user_auth_provider_row`
- `tests/libs/users/test_services.py` against the real test database

**Verify:** the service tests cover a first sign-in creating both rows, a returning
sign-in creating nothing, the inactive and email-conflict paths, and not found.

---

## Step 9 — Google sign-in

Needs a Google Cloud OAuth client — **manual setup by Tyler**. One client per
environment; "persona-blog local" has the redirect URI
`http://localhost:8000/auth/google/callback` (exact match, and `localhost` is not
`127.0.0.1`), scopes `openid email profile`, consent screen in Testing with Tyler as a
test user. Google redirects the browser, never calls the API, so localhost needs no
tunnel. `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are env-only secrets.

No JWT of our own: the cookie holds an opaque random token and Redis holds the state,
so logout is immediate. Google's ID token is the only JWT, and it arrives over TLS
straight from the token endpoint, so we check `aud`, `iss`, `exp` and the nonce rather
than re-fetching Google's keys. Library: `google-auth` for decoding that token, plus
`httpx` for the code exchange.

Build:

- `uv add google-auth`, and move `httpx` from the dev group to the dependencies
- `libs/auth/` — what isn't provider-specific:
  - `constants.py` — `SESSION_COOKIE_NAME = "sid"` and the Redis key prefixes
  - `settings.py` — `AuthSettings { session_ttl_seconds, oauth_state_ttl_seconds,
    frontend_url }`
  - `results.py` — `OAuthStateResult`, and `AuthUser { id, identity }`
  - `services/` — `AuthSessionService` (create, find, delete) and `OAuthStateService`
    (`create_state()` stores state, nonce and PKCE verifier; `consume_state()` reads and
    deletes, so a sign-in attempt can't be replayed)
- `libs/google_auth/` — everything Google-specific: `constants.py`, `settings.py`
  (`GoogleAuthSettings { redirect_url, request_timeout_seconds }`), `results.py`
  (`GoogleIdentityResult`, `GoogleSignInResult`), and `services/`:
  - `GoogleOAuthService.build_authorization_url()` and
    `.exchange_code_for_identity(code, state)`, which decodes the ID token and checks
    `aud`, `iss`, `exp` and the nonce
  - `GoogleSignInService.sign_in_with_google(code, state)` composes the flow: Google
    identity, then the user row through `UserService`, then the session. A route that
    would otherwise need another domain's service composes in a lib instead, so
    `domains/google_auth/` never imports `domains/users/`
- `apps/api/core/dependencies.py` — `AuthUserDep`, the guard: reads the cookie,
  resolves the session, and 401s otherwise. Routes needing auth take it and pass the
  `AuthUser` to services, which use `auth_user.id` for the audit columns. That's the
  Passport-equivalent: FastAPI has no strategy or guard registry, just dependencies
- `apps/api/domains/google_auth/` — `GET /auth/google/login` redirects to Google;
  `GET /auth/google/callback` signs in, sets the cookie and redirects to
  `frontend_url`. The cookie is httpOnly, `SameSite=Lax`, and `secure` outside
  `DEVELOPMENT`. A refused sign-in (403 inactive, 409 email taken) surfaces as that
  status code, not a redirect
- `apps/api/domains/auth/` — `POST /auth/logout` deletes the session and clears the
  cookie. A second sign-in provider later becomes its own lib and domain beside
  `google_auth`, so each domain keeps one `router.py`
- `apps/api/domains/users/` — `dtos.py`, `dependencies.py`, and `router.py` with
  `GET /users/me` (`find_signed_in_user`), guarded by `AuthUserDep` and calling
  `UserService.find_user_by_identity`. `/generate-text` takes the guard when it lands
  in step 13
- Tests: stubbed Google HTTP responses and ID tokens, never the real API; the session
  service against real Redis; the routes through the real guard

**Verify:** full browser round trip to a logged-in state. Cookie is httpOnly, and
`secure` is off only in dev. Call `/users/me` without the cookie and get a 401. Log
out, then confirm the Redis key is actually gone (`redis-cli KEYS 'session:*'`), not
just the cookie cleared.

**Deferred:** a refresh or sliding-expiry scheme, so a long session doesn't end
mid-use. The `state` record in Redis is also where a post-sign-in redirect path or an
invite token would live, and the callback would then send the browser somewhere other
than `frontend_url`.

---

## Step 10 — Sign-in and activity timestamps

No middleware. Auth resolves in `AuthUserDep`, so a middleware would run before it and
see nothing; the work happens where the signed-in user is already known. Sign-in
timestamps are part of the sign-in transaction, not background work: they are two
column updates in a request that already writes rows, and being atomic with the user
row beats being off the critical path. Only `last_activity_at` runs in the background,
because it happens on every authenticated request.

Build:

- `libs/users/` — `services/` package now that there are two services:
  - `UserService.find_or_create_user_from_auth_provider` also stamps `last_login_at` on
    `pb_user` and `last_used_at` on `pb_user_auth_provider`, in both the found and
    created branches. `FindOrCreateUserFromAuthProviderInput` gains `signed_in_at`, so
    the caller supplies the time and tests pass a literal
  - `UserActivityService.record_activity(user_id, activity_at)` — a Redis
    `SET NX EX` on `user-activity:<user_id>` throttles it to once per
    `activity_interval_seconds`; when it's due, one `UPDATE` sets `last_activity_at`
  - `settings.py` — `UserSettings { activity_interval_seconds }`, on `AppSettings`
  - `constants.py` — the Redis key prefix
- `apps/api/core/dependencies.py` — `get_auth_user` takes `BackgroundTasks` and
  schedules the activity update after resolving the session, so it never delays the
  response and never runs for a signed-out request
- `apps/api/core/background_tasks.py` — the task opens its own session from
  `app.state.db_session_factory` and owns its transaction. A request's session is
  closed by the time a background task runs, so it can't be reused
- Tests: the throttle writing once per interval, sign-in stamps in both branches, and
  the background task called directly. A route test can't prove the task ran: it opens
  a second session on the shared test connection and the harness loses that write,
  which is a harness limit, not a production one — verified against a pooled engine

**Verify:** sign in, call `/users/me` twice inside the interval, and confirm one
activity write and that `last_login_at` and `last_used_at` moved.

---

## Step 11 — Frontend auth

Sign-in only. The write screen waits for step 13, when there is an endpoint behind
it.

Build:

- Sign-in button hitting the backend login route
- A logged-in view showing `display_name` from `/users/me`
- Sign-out button posting to `/auth/logout`
- Vite dev proxy to the API so cookies are same-origin
- A typed API client module; no `fetch` calls scattered through components

**Verify:** sign in and see your `display_name`. Hard refresh mid-session and confirm
you stay signed in. Sign out, confirm the app returns to the signed-out view and a
direct call to `/users/me` 401s.

---

## Step 12 — LLM lib + dev LLM router

Outline only — detailed when this step starts.

Build:

- `libs/llm/` — `services.py` with `LlmService.complete()`, `settings.py` with
  `LlmSettings { model_name, request_timeout_seconds, max_output_tokens }`,
  `inputs.py`, `results.py` with
  `LlmCompletionResult { content, input_tokens, output_tokens }`
- API key from env via `AppSettings`, never TOML; add `OPENAI_API_KEY` to
  `.env.example`
- Every LLM call recorded in a tracking table. Columns and migration are planned
  when this step is detailed
- A dev-only router for making basic calls against different LLMs and checking each
  call is tracked. Registered only when `environment` is `DEVELOPMENT`
- Log token counts per call at info level
- Tests use a stub `LlmService`, never the real API

**Open when detailing:** which providers are in scope and whether that means a
provider abstraction now; the tracking table's columns; whether the dev router
requires sign-in.

**Verify:** call the dev router against more than one model, get real text back,
and confirm a tracking row per call with token counts. Remove the API key and confirm
a clean error response rather than a stack trace. `uv run pytest` passes with no
network.

---

## Step 13 — `generate_text` lib + domain

Outline only — detailed once step 12 has settled the LLM lib. This is the app's core
logic, built as a LangGraph workflow on top of `LlmService`.

Build:

- `libs/generate_text/` — `services.py` with `GenerateTextService.generate_text()`,
  `inputs.py` with `GenerateTextInput { text_type, prompt_text }`, `results.py` with
  `GenerateTextResult { content, character_count }`
- `TextType(StrEnum)` with the single member `BLOG_POST = "BLOG_POST"` in
  `libs/generate_text/types.py`
- `libs/generate_text/prompts.py` — `GenerateTextPrompt.build_system_prompt()` and
  `.build_user_prompt(prompt_text, text_type)`, templates as `UPPER_SNAKE` constants
- The LangGraph workflow. `langgraph` is a new dependency, confirmed when this step
  is detailed
- `GenerateTextService` takes an `LlmService` through `__init__`; the dependency
  factory wires it
- `apps/api/domains/generate_text/` — `dtos.py` with `GenerateTextDto` + `to_input()`
  and `GeneratedTextResponseDto` + `from_result()`, `dependencies.py`, `router.py` at
  `/generate-text`, guarded by `CurrentUserDep`
- Frontend write screen: a form posting to `/generate-text` through the typed API
  client and rendering the result
- Tests both sides: service called directly, route via the test client

**Verify:** sign in, generate text from the write screen, sign out, confirm the form
401s. Post an invalid `text_type` and confirm a readable 422. Confirm
`grep -r "from apps" libs/` returns nothing.

---

## Step 14 — Alpha limits + Logfire

Build:

- Per-user generation cap (3), Tyler's account exempt. Counter in Redis
- structlog → Logfire wiring, request-id middleware
- Railway deploy config

**Verify:** hit the cap on a test account and confirm a clear 429 with a useful
message. Confirm traces appear in Logfire.

---

## Deliberately deferred

Personas, saved posts and the blog feed, the human-in-the-loop review flow, the
un-AI-ify module, Anthropic as a second provider, scheduled publishing, RSS context.
Step 14 ends with a working single-user writing tool, which is the point at which
the persona model can be designed against something real.
