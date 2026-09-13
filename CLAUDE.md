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
uv lock --generate-hashes    # regenerate lockfile after dependency changes
uv run ruff check --fix .    # lint
uv run ruff format .         # format
uv run pytest                # tests
uv run granian --interface asgi apps.api.main:app --reload   # dev server
```

Run `ruff check` and `pytest` before proposing a commit.

## Non-obvious stack choices

granian (not uvicorn) · structlog → Logfire (not stdlib logging) · uv (not pip or
poetry) · async SQLAlchemy throughout · LangGraph for agent workflows · Pydantic
Settings from TOML, overridden by env vars.

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

## Git

- Commits are `type(domain): what was done` — e.g. `feat(humanizer): add AI-tell
rubric prompt`, `fix(persona): correct bio length validation`.
- Types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`.
- Domains are the business area touched: `humanizer`, `persona`, `post`, `user`,
  `auth`, `graph`, `db`, `infra`, `web`. Use one that already appears in the log
  before inventing a new one.
- Never commit unless asked. Never push to `main` directly.
- `CLAUDE.local.md` is gitignored — personal notes go there, not in this file.
