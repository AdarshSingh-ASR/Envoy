"""Envoy configuration.

All model access goes through LiteLLM so any provider works:
  - GROQ_API_KEY        + ENVOY_MODEL=groq/openai/gpt-oss-120b
  - OPENROUTER_API_KEY  + ENVOY_MODEL=openrouter/anthropic/claude-sonnet-4.5
  - GEMINI_API_KEY      + ENVOY_MODEL=gemini/gemini-3.6-flash
  - AWS credentials     + ENVOY_MODEL=bedrock/us.anthropic.claude-3-7-sonnet-20250219-v1:0
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL_ID = os.getenv("ENVOY_MODEL", "groq/openai/gpt-oss-120b")
API_KEY = os.getenv("ENVOY_API_KEY") or None  # optional explicit key override

# Tavily (optional real web search; strategy degrades gracefully without it)
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

DB_PATH = ROOT / "envoy.db"
SESSIONS_DIR = ROOT / "sessions"

OWNER_PROFILE = {
    "name": os.getenv("ENVOY_OWNER_NAME", "Alex Rivera"),
    "email": os.getenv("ENVOY_OWNER_EMAIL", "alex.rivera@example.com"),
    "timezone": os.getenv("ENVOY_OWNER_TZ", "Asia/Calcutta"),
}


def ensure_dirs() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
