# Based on: https://github.com/astral-sh/uv-docker-example/blob/main/standalone.Dockerfile

# First, build the application in the `/app` directory
from ghcr.io/astral-sh/uv:trixie-slim as builder
env UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Configure the Python directory so it is consistent
env UV_PYTHON_INSTALL_DIR=/python

# Only use the managed Python version
env UV_PYTHON_PREFERENCE=only-managed

# Install Python before the project for caching
run uv python install 3.13

workdir /app
run --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --group docker
copy app.py pyproject.toml uv.lock .
run --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --group docker

# Then, use a final image without uv
from debian:trixie-slim

# Setup a non-root user
run groupadd --system --gid 999 pyapp \
 && useradd --system --gid 999 --uid 999 --create-home pyapp

# Copy the Python version
copy --from=builder --chown=python:python /python /python

# Copy the application from the builder
copy --from=builder --chown=pyapp:pyapp /app /app

# Use `/app` as the working directory
workdir /app

# Place executables in the environment at the front of the path
env PATH="/app/.venv/bin:$PATH"

# So logs show up immediately
env PYTHONUNBUFFERED=1

# Use the non-root user to run our application
user pyapp

# Run the flask app (our dependency group "Docker" called for granian to be installed)
entrypoint [ \
    "granian", \
    "--interface", "wsgi", \
    "--host", "0.0.0.0", \
    "--workers", "2", \
    "--blocking-threads", "8", \
    "--backpressure", "32", \
    "app:app" \
]
