from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = "http://localhost:11434"
    searxng_url: str = "http://localhost:5300"
    model: str = "qwen3.8:27b"
    runs_dir: Path = Path("runs")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        return cls(
            ollama_base_url=env.get("OLLAMA_BASE_URL", cls.ollama_base_url),
            searxng_url=env.get("SEARXNG_URL", cls.searxng_url),
            model=env.get("DR_MODEL", cls.model),
            runs_dir=Path(env.get("DR_RUNS_DIR", "runs")),
        )
