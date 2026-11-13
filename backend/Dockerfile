# The API image. Railway builds it with backend/ as the root directory.

FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so a code change reuses this layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .

# The venv's launchers name /app/.venv/bin/python, so the runtime keeps the same path
FROM python:3.14-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    GRANIAN_INTERFACE=asgi \
    GRANIAN_HOST=:: \
    GRANIAN_PORT=8000 \
    GRANIAN_WORKERS=1 \
    GRANIAN_WORKERS_KILL_TIMEOUT=170 \
    GRANIAN_RESPAWN_FAILED_WORKERS=true
USER app
EXPOSE 8000
# Exec form, so granian is PID 1 and receives Railway's SIGTERM
CMD ["granian", "apps.api.main:app"]
