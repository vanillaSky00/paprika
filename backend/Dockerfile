### Stage 1: dependency build stage ###
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Tells uv to compile .pyc bytecode during install.
ENV UV_COMPILE_BYTECODE=1
ENV UV_PROJECT_ENVIRONMENT="/venv"


COPY pyproject.toml uv.lock ./

ARG INSTALL_LOCAL=false

RUN if [ "$INSTALL_LOCAL" = "true" ]; then \
    uv sync --frozen --no-install-project --no-dev --group local; \
    else \
    uv sync --frozen --no-install-project --no-dev; \
    fi

### Stage 2: runtime image ###
FROM python:3.11-slim

WORKDIR /app

# From previous stage we only want its /app/.venv, the output of uv sync
COPY --from=builder /venv /venv

ENV PATH="/venv/bin:$PATH"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
