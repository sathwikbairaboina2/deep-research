FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    DR_RUNS_DIR=/data/runs

WORKDIR /app

# Dependencies first so code edits do not rebuild this layer.
COPY pyproject.toml uv.lock README.md ./
COPY packages/quoteproof/pyproject.toml packages/quoteproof/README.md packages/quoteproof/
RUN uv sync --frozen --no-install-workspace

COPY . .
RUN uv sync --frozen \
    && useradd --create-home app \
    && mkdir -p /data/runs \
    && chown -R app:app /app /data

USER app
ENTRYPOINT ["dr"]
CMD ["--help"]
