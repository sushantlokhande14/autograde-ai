# Autograde AI — API gateway (dev overlay image).
# The base stack runs infra only; this image lets the API also run in-container.
FROM python:3.11-slim

# uv for fast, lockfile-driven installs.
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /bin/

WORKDIR /app

# Copy the workspace (root + libs + services). .dockerignore keeps data/ out.
COPY . /app

# Resolve and install the workspace into an in-image virtualenv.
RUN uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
