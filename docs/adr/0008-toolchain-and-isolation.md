# ADR-0008: Host `uv` for the dev loop, Docker for SearXNG and app parity

- Status: accepted (2026-10-04)

## Context
The design wanted every Python command in containers. The host already has `uv 0.12.21` and CPython 3.12, and a bind-mounted container venv on Windows is slow. Go is the missing language on this host, not Python.

## Decision
- Dev loop and CI: `uv sync`, `uv run pytest`, `uv run ruff`, `uv run dr ...` with the repo's own `.venv`.
- Docker: `docker-compose.yml` (project `deep-research`) runs `searxng/searxng:2026.10.2-19ffbcd30` as `deep-research-searxng` on `127.0.0.1:5300`. It builds `deep-research-app` from `python:3.12-slim-bookworm` with `uv` copied from `ghcr.io/astral-sh/uv:0.12.21`. The app reaches host Ollama at `http://host.docker.internal:11434` (checked 2026-10-04: `{"version":"0.35.1"}`).
- On this host, Windows Application Control blocks the generated `.venv/Scripts/dr.exe` launcher (os error 4551, seen 2026-10-04), so host commands use `uv run python -m deep_research`. The `dr` script still ships and works in Docker and CI.
- `dr serve` defaults to `127.0.0.1:5301`. Only host ports 5300-5309 are used.
- The SearXNG secret comes from `SEARXNG_SECRET` with a non-secret local default. No `.env` is committed.

## What I gave up
- Bit-for-bit parity between the host venv and the image. The image runs the same test suite as a gate to catch drift.
