"""Every knob the engine exposes, read from the environment.

Swapping the brain is a config change, not a code change:

  # Anthropic (default)
  RTS_PROVIDER=anthropic
  RTS_MODEL=claude-haiku-4-5
  ANTHROPIC_API_KEY=sk-ant-...

  # Anything speaking the OpenAI chat-completions API — local or hosted.
  # Ollama, LM Studio, vLLM, llama.cpp, Together, Groq, OpenRouter, ...
  RTS_PROVIDER=openai
  RTS_BASE_URL=http://localhost:11434/v1
  RTS_MODEL=llama3.1
  RTS_API_KEY=whatever          # local servers ignore it, but some want it set

  # No network at all — deterministic stub, for tests and offline dev.
  RTS_PROVIDER=stub
"""

import os

PROVIDER = os.environ.get("RTS_PROVIDER", "anthropic").strip().lower()
MODEL = os.environ.get("RTS_MODEL", "claude-haiku-4-5").strip()
MAX_TOKENS = int(os.environ.get("RTS_MAX_TOKENS", "1024"))

# OpenAI-compatible providers only.
BASE_URL = (os.environ.get("RTS_BASE_URL") or "").rstrip("/")
API_KEY = os.environ.get("RTS_API_KEY", "")

# Anthropic only. Leave unset for Haiku 4.5 — it rejects the effort parameter with a
# 400. Set to low/medium/high if you swap to a model that supports it (Sonnet 5, Opus).
EFFORT = (os.environ.get("RTS_EFFORT") or "").strip() or None
