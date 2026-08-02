"""Every knob the engine exposes, read from the environment.

Swapping the brain is a config change, not a code change:

  # Anthropic (default)
  RTS_PROVIDER=anthropic
  RTS_MODEL=claude-sonnet-5
  ANTHROPIC_API_KEY=sk-ant-...

  # Cheaper and faster, at the cost of the judgment calls. Haiku rejects both the
  # effort and thinking parameters, so blank them out.
  RTS_MODEL=claude-haiku-4-5
  RTS_EFFORT=
  RTS_THINKING=

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
MODEL = os.environ.get("RTS_MODEL", "claude-sonnet-5").strip()

# Covers thinking AND the reply, so it can't be sized against the reply alone. The bubble
# text is tiny; the headroom here is for the reasoning behind it.
MAX_TOKENS = int(os.environ.get("RTS_MAX_TOKENS", "4096"))

# OpenAI-compatible providers only.
BASE_URL = (os.environ.get("RTS_BASE_URL") or "").rstrip("/")
API_KEY = os.environ.get("RTS_API_KEY", "")

# Anthropic only. low | medium | high | xhigh | max. Judging relatedness is the hard part
# of a turn, so this is the main quality dial — but the reply still has to arrive while
# someone is watching a typing indicator, which is why the default isn't higher.
EFFORT = (os.environ.get("RTS_EFFORT") or "medium").strip() or None

# Anthropic only. "adaptive" or "disabled". Adaptive is also the default on Sonnet 5 and
# Opus 5 when omitted, so this mostly exists to turn thinking OFF for a cheap model.
# Haiku 4.5 rejects both this and EFFORT — set RTS_THINKING= and RTS_EFFORT= for it.
THINKING = (os.environ.get("RTS_THINKING") or "adaptive").strip() or None

# Anthropic only. Max web searches the bot may run in one turn; 0 turns it off. Server
# side, so there is nothing to execute locally -- but each one costs seconds of a turn
# somebody is waiting on, which is why the ceiling is low and the prompt says to reach
# for it rarely.
SEARCH = int(os.environ.get("RTS_SEARCH", "2"))
