# Persona Blog

An AI-agent app that writes blog posts in the voice of personas you create, with a
human reviewing each step before anything is published.

You define a persona: a pen name, a bio, a background, a writing style and a sample of
their writing. Then you ask it for a post. A LangGraph workflow writes an outline, a
draft and a humanized final pass, each in the persona's voice. Any step can pause for
your review: approve it, or send feedback and the step is rewritten. The finished post
is saved, and you choose whether to keep it as a draft, publish it now or schedule it.

## How it works

```
React + Vite ──/api──▶ FastAPI ──▶ LangGraph workflow ──▶ OpenAI
   (5173)              (8000)       outline → draft → humanize
                         │              each step can pause for review
                         ├──▶ Postgres   personas, posts, runs, every LLM call
                         └──▶ Redis      sessions, workflow checkpoints
```

- **Human in the loop.** A run that reaches a step held for review stops, and its state
  is checkpointed in Redis. Approving or sending feedback resumes it from there, so
  nothing waits in memory between requests.
- **Checked output.** Every step that writes the post body has to return Markdown in
  the post format (one title, `##`/`###` headings, no raw HTML). The format is checked
  in code; output that fails is retried once with the problems listed, then the run
  fails cleanly.
- **Cost tracking.** Every LLM call is stored with its prompts, tokens and cost, and
  each run totals its own.
- **Personas shape every prompt.** Each step builds its own system prompt from the
  persona fields it needs, plus the tone and audience for that post.

## Stack

| Layer    | Choices                                                                     |
| -------- | --------------------------------------------------------------------------- |
| Backend  | Python 3.14, FastAPI on granian, async SQLAlchemy, LangGraph, Pydantic Settings, structlog, uv |
| Data     | Postgres 18 with hand-written SQL migrations run through Alembic; Redis 8  |
| Frontend | React 19, Vite, TypeScript, TanStack Query and Form, Zod, Tailwind v4, shadcn/ui |
| API      | Frontend types generated from FastAPI's OpenAPI schema (`openapi-typescript`) |
| Auth     | Google sign-in, with server-side sessions in Redis behind an httponly cookie |
| CI       | GitHub Actions: lint, format, tests, a migration stairway test and a schema drift check |

## Running it locally

Postgres and Redis run in Docker. The API and the frontend run in your terminal, so
they reload on save and are easy to debug.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose
- [uv](https://docs.astral.sh/uv/), which installs the right Python (3.14) for you
- Node 22 and npm
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A Google OAuth client, for signing in:
  1. In the [Google Cloud console](https://console.cloud.google.com/apis/credentials),
     create an OAuth client ID of type **Web application**
  2. Add `http://localhost:8000/auth/google/callback` as an authorized redirect URI
  3. Keep the client ID and secret for the next step

### 1. Configure the backend

```bash
cd backend
cp .env.example .env
```

[`backend/.env.example`](backend/.env.example) lists the values you need. Most are
already filled in for the Docker containers. You supply three, all your own:

| Variable               | Where it comes from                         | Cost                     |
| ---------------------- | ------------------------------------------- | ------------------------ |
| `OPENAI_API_KEY`       | Your OpenAI account                         | Pay per use: every post you generate is billed to it |
| `GOOGLE_CLIENT_ID`     | The OAuth client from the prerequisites     | Free                     |
| `GOOGLE_CLIENT_SECRET` | The same OAuth client                       | Free                     |

The OpenAI key is the only one that costs anything. The Google client is needed only
because sign-in is through Google. `.env` is gitignored, so your keys stay on your
machine.

Settings come from `config.toml`, overridden by environment variables and `.env`.
Nested settings use a double underscore, such as `AUTH__SESSION_TTL_SECONDS`.

#### Choosing the models

Each step asks for a tier of model rather than a specific one, and each tier has a
default:

| Tier       | Used for                                          | Default       | Variable                    |
| ---------- | ------------------------------------------------- | ------------- | --------------------------- |
| `FAST`     | The outline and its rewrites                      | `gpt-4o-mini` | `LLM__FAST__MODEL_NAME`     |
| `STRONG`   | The draft, the humanize pass and their rewrites   | `gpt-5.6-sol` | `LLM__STRONG__MODEL_NAME`   |
| `THINKING` | Not used yet                                      | `o3`          | `LLM__THINKING__MODEL_NAME` |

To keep costs down while you try it out, run every step on the cheaper model by
adding this to `.env` (it's in `.env.example`, commented out):

```bash
LLM__STRONG__MODEL_NAME=gpt-4o-mini
```

Each tier's output limit and timeout can be set the same way, for example
`LLM__STRONG__MAX_OUTPUT_TOKENS` and `LLM__STRONG__REQUEST_TIMEOUT_SECONDS`. Run costs
are worked out from a price table for the default models. A model that isn't in it
still works, but its runs show the cost as unknown.

### 2. Start Postgres and Redis

```bash
docker compose up -d
```

This starts Postgres on port **5437** and Redis on port **6387**. The ports are
non-default so they don't clash with a Postgres or Redis you already run. The first
start also creates a `pb_test` database for the test suite.

### 3. Install, migrate and start the API

```bash
uv sync                                                      # install from the lockfile
uv run alembic upgrade head                                  # create the tables
uv run granian --interface asgi apps.api.main:app --reload   # http://localhost:8000
```

API docs are at http://localhost:8000/docs.

### 4. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

Vite proxies `/api/*` to the API, so the browser sees a single origin and the session
cookie needs no CORS. Open http://localhost:5173 and sign in with Google.

### Stopping and resetting

```bash
docker compose stop        # stop the containers, keep the data
docker compose down -v     # remove the containers and their data, for a clean start
```

After `down -v`, run `uv run alembic upgrade head` again.

## Development

### Backend, from `backend/`

```bash
uv run ruff check --fix .                        # lint
uv run ruff format .                             # format
uv run pytest                                    # tests, against pb_test
uv run pytest -m migration                       # migration stairway test
uv run python -m scripts.db.check_schema_drift   # Orm classes vs the migrated schema
```

The tests need the Docker containers running. They use the `pb_test` database and
Redis database 15, so they never touch your local data, and they stub the LLM, so they
cost nothing.

`scripts/e2e/` holds end-to-end scripts that walk each feature's API against your
running dev server: personas, generation with review, and blog posts. Run one from
`backend/` with `./scripts/e2e/personas.sh`. They sign in as you without a
browser, so sign in through the app once first. The generation scripts make real
OpenAI calls. They refuse to run unless `.env` points at a local development database.

### Frontend, from `frontend/`

```bash
npm run fmt          # format with oxfmt
npm run lint         # oxlint
npm run build        # type-check and build
npm run api:types    # regenerate API types (needs the API running)
```

## Project layout

```
backend/
├── apps/api/        FastAPI app: routers, DTOs and dependencies, one folder per domain
├── libs/            the domain logic: services, LangGraph graphs and prompts, Orm classes
├── migrations/      hand-written .up.sql / .down.sql pairs, run through Alembic
├── scripts/         db/ for the schema drift check, e2e/ for end-to-end API scripts
└── tests/           pytest, against a real Postgres and Redis
frontend/src/
├── features/        one folder per area: api hooks, components, form schemas
├── routes/          one file per page, composing features
└── components/      shared UI: shadcn/ui, the form layer, layout
plans/plan.md        the build plan, step by step
```

## Built with Claude Code

This project is built with [Claude Code](https://claude.com/claude-code) as a pair
programmer, set up so it writes code the way the project does:

- [`CLAUDE.md`](CLAUDE.md) holds the commands, the git and PR conventions, and how work
  is split across agents.
- [`.claude/rules/`](.claude/rules) holds the conventions for each side of the stack,
  such as FastAPI structure, naming, database, testing, React structure and styling.
- [`.claude/agents/`](.claude/agents) holds specialised agents that write code to those
  rules (schema, FastAPI, React, tests), and auditors that keep the rules consistent
  with each other.
- [`plans/plan.md`](plans/plan.md) records each feature's design before it's built.

## License

[MIT](LICENSE)
