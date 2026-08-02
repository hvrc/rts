"""Anthropic brain — a single structured-output call per turn."""

import json

from .. import config
from ..schema import MOVE_SCHEMA
from .base import Provider


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model=None, max_tokens=None, effort=None, thinking=None):
        self.model = model or config.MODEL
        self.max_tokens = max_tokens or config.MAX_TOKENS
        self.effort = effort if effort is not None else config.EFFORT
        self.thinking = thinking if thinking is not None else config.THINKING
        self._client = None

    def _client_lazy(self):
        # Deferred so the deterministic paths (letter rule, duplicates, reset) still
        # work with no API key configured.
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def move(self, system_prompt, messages, ctx=None):
        # ctx is unused: the rule and the board are already spelled out in the prompt.
        output_config = {"format": {"type": "json_schema", "schema": MOVE_SCHEMA}}
        if self.effort:
            output_config["effort"] = self.effort

        request = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": [{
                "type": "text",
                "text": system_prompt,
                # The system prompt is fixed for a session and the transcript only ever
                # grows at the end, so everything up to here is a stable prefix. Sonnet 5
                # caches from 1024 tokens; the layered prompt clears that comfortably.
                "cache_control": {"type": "ephemeral"},
            }],
            "output_config": output_config,
            "messages": messages,
        }
        # Judging whether two words are related is the one genuinely hard call in a turn,
        # and it was being made with reasoning switched off. Leave thinking on unless a
        # model is configured that can't do it — and note that disabling it on Sonnet 5
        # or Opus 5 also risks a tool call arriving as plain text, which would silently
        # never run.
        if self.thinking:
            request["thinking"] = {"type": self.thinking}

        resp = self._client_lazy().messages.create(**request)
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)
