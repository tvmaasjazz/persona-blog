# Project

AI-agent app that generates personas and their blog posts, with human-in-the-loop
review.

## Layout

```
frontend/            React + Vite app
backend/
└── apps/api/        FastAPI service (more services will land beside it)
plans/               build plans — committed to the repo
```

Save plans to `plans/`. The folder is committed and published with the repo, so
plans can be referenced from other files — and must not contain secrets or
anything you wouldn't push to GitHub.

## Commands

Run from `backend/`:

```bash
uv sync                      # install from lockfile
docker compose up -d         # Postgres + Redis; the dev server and tests need them
uv lock                      # regenerate lockfile after dependency changes (hashes included)
uv run ruff check --fix .    # lint
uv run ruff format .         # format
uv run pytest                # tests
uv run pytest -m migration   # migration stairway test (rebuilds the test schema)
uv run alembic upgrade head  # apply migrations to the database in .env
uv run python -m scripts.check_schema_drift  # Orm metadata vs the migrated schema
uv run granian --interface asgi apps.api.main:app --reload   # dev server
```

Run from `frontend/`:

```bash
npm install                  # install from package-lock.json
npm run dev                  # dev server at http://localhost:5173
npm run fmt                  # format with oxfmt
npm run fmt:check            # check formatting without writing
npm run lint                 # oxlint
npm run build                # type-check and build to dist/
npx shadcn@latest add <name> # add a shadcn/ui component to src/components/ui/
```

Before committing, run `ruff check` for backend changes, and `npm run fmt:check`,
`npm run lint` and `npm run build` for frontend changes. `pytest` must pass before
the PR is ready to merge (see Pull requests).

### Commands for Tyler to run

When something takes more than one command to check — curl calls that chain, a
sequence that carries a value from one step to the next, setup followed by a query —
it ships as one script in `backend/scripts/`, run with a single command. Never a list
of commands to paste in order.

The script prints each step and what came back, checks what it can and says which
expectation failed, and fails early with the fix when a prerequisite is missing, such
as a dev server that isn't running. `backend/scripts/verify_generate_text.sh` is the
pattern.

## Non-obvious stack choices

granian (not uvicorn) · structlog → Logfire (not stdlib logging) · uv (not pip or
poetry) · async SQLAlchemy throughout · LangGraph for agent workflows · Pydantic
Settings from TOML, overridden by env vars. On the frontend: npm (not pnpm or
yarn) · oxlint and oxfmt (not ESLint or Prettier), with oxfmt pinned to an exact
version because it's pre-1.0.

Ask before adding a dependency.

## Keeping the rules current

The conventions in `.claude/rules/` are the source of truth for how code here is
written. They are expected to grow.

- When a human developer corrects something you wrote, ask whether the correction is a one-off or
  a general rule. If it's general, propose the exact wording to add or change in the
  relevant rules file, and which file it belongs in.
- When you hit a situation the rules don't cover and have to make a judgement call,
  say so in your summary and propose a rule for it. Don't quietly pick a convention.
- When a change contradicts an existing rule, flag the contradiction and ask which
  wins rather than following the newer instruction and leaving the file stale.
- When a rules change adds, removes, or moves a kind of file, check `.claude/agents/`
  and `.claude/commands/` for anything that scopes work by file type, and propose
  matching edits to their descriptions and scope lists.
- Propose the edit; don't apply it unless asked.
- Before a PR that changes `.claude/rules/`, `.claude/agents/`, or
  `.claude/commands/` is ready to merge, run the auditor for each side the change
  touches on the changed files: `be-docs-auditor` for the backend, `fe-docs-auditor` for the
  frontend. Pass each one only its own side's files; they skip the other side's
  silently, so a file in neither list goes unaudited. Fix what each finds in those
  files, and report the rest. Plan edits and small wording changes skip it.

## Agents

An agent in `.claude/agents/` is named for the side of the stack it works on:

- `react-` for frontend agents that write or review React code: `react-coder`
- `fe-` for other frontend work, such as styling or the frontend docs: `fe-docs-auditor`
- `be-` for backend agents: `be-test-writer`, `be-docs-auditor`. Agents named for a
  backend tool, `fastapi-coder` and `schema-coder`, keep the tool name instead

### Running agents in parallel

Split work across parallel agents only along files they don't share.

- **Code.** `schema-coder` runs alone first; everything else needs its Orm classes.
  Then `fastapi-coder` agents split by lib or domain. When one part calls another,
  write the contract first (names, signatures, `Input`/`Result` classes, exceptions)
  and give both agents the identical text. One agent owns each shared wiring file
  (`app_factory.py`, `core/dependencies.py`, `orm/__init__.py`). Afterwards, check
  the calls match the contract, then run ruff and import the app.
- **Tests.** One `be-test-writer` adds the shared factories, stubs and fixtures first.
  Then two or three run in parallel on separate test files, each running only its
  own files: never the full suite, never `pytest -m migration`, since they share the
  `pb_test` database. Run the full suite and the migration test once at the end.

## Pull requests

Open the PR for review as soon as the code is written and `ruff check` passes, before
tests and the docs audit. Tests, then audit fixes, land afterwards as separate commits
on the same PR. Until they do, the PR description says what's still to come and which
existing tests fail.

## Git

- Commits are `type(domain): what was done` — e.g. `feat(humanizer): add AI-tell
rubric prompt`, `fix(persona): correct bio length validation`.
- Types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`.
- Domains are the business area touched: `humanizer`, `persona`, `post`, `user`,
  `auth`, `graph`, `db`, `infra`, `web`. Use one that already appears in the log
  before inventing a new one.
- Branches are `type/what-it-does`, using the commit types — e.g.
  `feat/setup-api-skeleton`, `fix/bio-length-validation`.
- Never commit unless asked. Never push to `main` directly.
- `CLAUDE.local.md` is gitignored — personal notes go there, not in this file.
