FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
RUN uv sync --locked

CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--port", "8001", "--host", "0.0.0.0"]
