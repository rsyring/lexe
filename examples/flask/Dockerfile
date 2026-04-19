# Based on: https://github.com/astral-sh/uv-docker-example/blob/main/standalone.Dockerfile

FROM python:3.13-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

RUN python -m pip install --no-cache-dir uv

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --group docker
COPY app.py pyproject.toml uv.lock ./
COPY hooks ./hooks
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --group docker

FROM python:3.13-slim

RUN groupadd --system --gid 999 pyapp \
 && useradd --system --gid 999 --uid 999 --create-home pyapp

RUN mkdir -p /home/pyapp/data \
 && chown -R pyapp:pyapp /home/pyapp

COPY --from=builder --chown=pyapp:pyapp /app /app

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

USER pyapp
EXPOSE 8000

ENTRYPOINT ["granian", "--interface", "wsgi", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--blocking-threads", "8", "--backpressure", "32", "app:app"]
