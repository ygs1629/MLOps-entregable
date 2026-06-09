"""Shared model selection helper for the ADK tutorial-style agents.

The course examples import ``tutorials.model_config.get_model``.  This project
keeps that public helper locally so ADK Web can import the agent without needing
the original tutorial repository on ``PYTHONPATH``.
"""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_MODEL = "gemini-2.5-flash"


def _load_env_file() -> None:
    """Load .env values while preserving already exported variables."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_model() -> str:
    """Return the ADK model configured through MODEL_PROVIDER.

    Supported local setup:
    - MODEL_PROVIDER=gemini: uses Google AI Studio with GOOGLE_API_KEY.
    - MODEL_PROVIDER=vertexai: uses Vertex AI credentials configured in env.

    Groq requires google-adk[extensions]/LiteLLM, which is not installed in the
    current lockfile, so we fail fast with an actionable message.
    """
    _load_env_file()
    provider = os.getenv("MODEL_PROVIDER", "gemini").strip().lower()

    if provider == "gemini":
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY is required when MODEL_PROVIDER=gemini.")
        return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

    if provider in {"vertex", "vertexai", "vertex_ai"}:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        if not os.getenv("GOOGLE_CLOUD_PROJECT"):
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is required when MODEL_PROVIDER=vertexai."
            )
        return os.getenv("VERTEXAI_MODEL", DEFAULT_VERTEX_MODEL)

    if provider == "groq":
        raise ValueError(
            "MODEL_PROVIDER=groq requires google-adk[extensions]/LiteLLM. "
            "Use MODEL_PROVIDER=gemini for the current environment or add the "
            "ADK extensions dependency."
        )

    raise ValueError(
        "Unsupported MODEL_PROVIDER. Use one of: gemini, vertexai, groq."
    )
