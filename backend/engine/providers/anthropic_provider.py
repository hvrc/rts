"""Anthropic brain — a single structured-output call per turn."""

import json

from .. import config
from ..schema import MOVE_SCHEMA
from .base import Provider


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model=None, max_tokens=None, effort=None):
        self.model = model or config.MODEL
        self.max_tokens = max_tokens or config.MAX_TOKENS
        self.effort = effort if effort is not None else config.EFFORT
        self._client = None

    def _client_lazy(self):
        # Deferred so the deterministic paths (letter rule, duplicates, reset) still
        # work with no API key configured.
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def move(self, system_prompt, user_message, ctx=None):
        # ctx is unused: the rule and the board are already spelled out in the prompt.
        output_config = {"format": {"type": "json_schema", "schema": MOVE_SCHEMA}}
        # Haiku 4.5 returns a 400 for `effort`; models that support it opt in via env.
        if self.effort:
            output_config["effort"] = self.effort

        resp = self._client_lazy().messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[{
                "type": "text",
                "text": system_prompt,
                # No-op below Haiku 4.5's 4096-token minimum cacheable prefix — the
                # prompt is ~1.4k today, so nothing is actually cached. Left in place
                # so it starts paying off if the prompt grows.
                "cache_control": {"type": "ephemeral"},
            }],
            thinking={"type": "disabled"},
            output_config=output_config,
            messages=[{"role": "user", "content": user_message}],
        )
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)
