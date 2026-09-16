# Persona Blog

An AI-agent app that generates personas and their blog posts, with a human reviewing
each post before it's published. The backend is a FastAPI service built on async
SQLAlchemy and LangGraph. The frontend is a React + Vite app.

## Run

Backend, from `backend/`:

```bash
uv sync                                                      # install from lockfile
cp .env.example .env                                         # local connection settings
docker compose up -d                                         # Postgres + Redis
uv run granian --interface asgi apps.api.main:app --reload   # dev server
uv run ruff check --fix .                                    # lint
uv run ruff format .                                         # format
uv run pytest                                                # tests
```

Frontend, from `frontend/`:

```bash
npm install
npm run dev
```
