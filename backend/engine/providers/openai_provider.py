"""OpenAI-compatible brain — covers local and open-source models.

Anything exposing POST {base_url}/chat/completions works: Ollama, LM Studio, vLLM,
llama.cpp's server, Together, Groq, OpenRouter, OpenAI itself. Point RTS_BASE_URL at
it and go.

Uses stdlib urllib so running a local model adds no Python dependency.

Structured output support varies wildly across these servers, so we degrade in three
steps rather than assuming: strict json_schema -> plain json_object -> bare prompting.
Whatever comes back is parsed defensively, because a 7B model will happily wrap its
JSON in prose or a ```json fence.
"""

import json
import re
import urllib.error
import urllib.request

from .. import config
from ..schema import MOVE_SCHEMA
from .base import Provider

_JSON_NUDGE = (
    "\n\nReturn ONLY a single JSON object matching this schema, with no prose and no "
    "code fence:\n" + json.dumps(MOVE_SCHEMA)
)


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, model=None, base_url=None, api_key=None, max_tokens=None):
        self.model = model or config.MODEL
        self.base_url = (base_url or config.BASE_URL).rstrip("/")
        self.api_key = api_key or config.API_KEY
        self.max_tokens = max_tokens or config.MAX_TOKENS
        if not self.base_url:
            raise ValueError("RTS_BASE_URL is required when RTS_PROVIDER=openai")

    def _post(self, payload):
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                # Local servers ignore this; hosted ones require it.
                "Authorization": f"Bearer {self.api_key or 'not-needed'}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    def move(self, system_prompt, messages, ctx=None):
        # ctx is unused: the rule and the board are already spelled out in the prompt.
        base = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
        }

        # Best to worst. Servers that don't understand a response_format 400 on it, so
        # try the strict form first and fall back rather than probing capabilities.
        attempts = [
            {**base, "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "rts_move", "strict": True, "schema": MOVE_SCHEMA},
            }},
            {**base, "response_format": {"type": "json_object"}},
            {**base, "messages": [
                {"role": "system", "content": system_prompt + _JSON_NUDGE},
                *messages,
            ]},
        ]

        last_error = None
        for payload in attempts:
            try:
                data = self._post(payload)
            except urllib.error.HTTPError as e:
                last_error = e
                continue  # server rejected this response_format — try a looser one
            return _parse_move(data["choices"][0]["message"]["content"])

        raise RuntimeError(f"all chat/completions attempts failed: {last_error}")


def _parse_move(content):
    """Pull a JSON object out of whatever the model said.

    Small local models fence their JSON, prefix it with "Sure!", or trail a sentence
    after it. Try the clean parse, then dig out the outermost {...}.
    """
    text = (content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in model output: {content!r}")
    return json.loads(text[start:end + 1])
