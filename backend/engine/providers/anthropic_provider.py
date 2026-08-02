"""Anthropic brain - a single structured-output call per turn."""

import json

from .. import config
from ..schema import MOVE_SCHEMA
from ..streaming import FieldReader
from .base import Provider

# Only these are forwarded out of the scanner. With web search on, the model narrates
# around the results in its own text blocks, and an allowlist keeps a stray quoted
# phrase in that narration from being mistaken for a field.
_FIELDS = ("response_code", "their_word", "chosen_word", "response")

# A paused turn should resume in one hop; more than a couple means something is wrong.
_MAX_RESUMES = 3


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, model=None, max_tokens=None, effort=None, thinking=None,
                 search=None):
        self.model = model or config.MODEL
        self.max_tokens = max_tokens or config.MAX_TOKENS
        self.effort = effort if effort is not None else config.EFFORT
        self.thinking = thinking if thinking is not None else config.THINKING
        self.search = search if search is not None else config.SEARCH
        self._client = None

    def _client_lazy(self):
        # Deferred so the deterministic paths (letter rule, duplicates, reset) still
        # work with no API key configured.
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def _request(self, system_prompt, messages, schema):
        """The request body. Shared by the streaming and non-streaming paths so the two
        can't drift - in particular so both keep the same cached prefix."""
        output_config = {"format": {"type": "json_schema", "schema": schema}}
        if self.effort:
            output_config["effort"] = self.effort

        request = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": [{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            "output_config": output_config,
            "messages": messages,
        }
        if self.search:
            request["tools"] = [{
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": self.search,
            }]
        if self.thinking:
            request["thinking"] = {"type": self.thinking}
        return request

    def stream_move(self, system_prompt, messages, ctx=None, schema=None):
        """Yield the move as it is written. See Provider.stream_move for the protocol.

        The reader is reset at each text block rather than run across the whole stream:
        with search enabled the model narrates around the results in separate blocks,
        and a single scanner spanning all of them would read that prose as part of the
        JSON. The last block that parses is the move, which is the same rule the
        non-streaming path uses.
        """
        request = self._request(system_prompt, messages, schema or MOVE_SCHEMA)
        client = self._client_lazy()

        with client.messages.stream(**request) as stream:
            reader, buffer = FieldReader(), ""
            for event in stream:
                if event.type == "content_block_start":
                    if getattr(event.content_block, "type", None) == "text":
                        reader, buffer = FieldReader(), ""

                elif event.type == "content_block_delta":
                    if getattr(event.delta, "type", None) != "text_delta":
                        continue          # thinking deltas are not ours to forward
                    text = event.delta.text
                    buffer += text
                    for name, delta, complete in reader.feed(text):
                        if name not in _FIELDS:
                            continue
                        if complete:
                            yield "field", (name, reader.values[name])
                        elif name == "response":
                            yield "delta", delta

            yield "done", _parse_move(stream.get_final_message())

    def move(self, system_prompt, messages, ctx=None, schema=None):
        # ctx is unused: the rule and the board are already spelled out in the prompt.
        output_config = {"format": {"type": "json_schema", "schema": schema or MOVE_SCHEMA}}
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

        # Runs on Anthropic's side, so there's no execution loop to write - but it does
        # cost seconds, and someone is watching a typing indicator. The prompt is what
        # keeps it rare: it's for justifications that turn on something the model has no
        # way to know, not for looking up whether two ordinary words are related.
        if self.search:
            request["tools"] = [{
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": self.search,
            }]
        # Judging whether two words are related is the one genuinely hard call in a turn,
        # and it was being made with reasoning switched off. Leave thinking on unless a
        # model is configured that can't do it - and note that disabling it on Sonnet 5
        # or Opus 5 also risks a tool call arriving as plain text, which would silently
        # never run.
        if self.thinking:
            request["thinking"] = {"type": self.thinking}

        client = self._client_lazy()
        resp = client.messages.create(**request)

        # A long server-tool turn can stop early and ask to be continued. Send it straight
        # back to pick up where it left off; without this the turn returns half-finished
        # and the JSON is simply missing.
        for _ in range(_MAX_RESUMES):
            if resp.stop_reason != "pause_turn":
                break
            request["messages"] = [*messages, {"role": "assistant", "content": resp.content}]
            resp = client.messages.create(**request)

        return _parse_move(resp)


def _parse_move(resp):
    """Pull the structured move out of the response.

    Taking the first text block was fine when a response was only ever one block. With
    search in play the model narrates around the results, so the JSON is the *last* text
    block rather than the first - and search result blocks sit in between. Work backwards
    and take the first thing that parses.
    """
    blocks = [b for b in resp.content if b.type == "text"]
    for block in reversed(blocks):
        try:
            return json.loads(block.text)
        except (json.JSONDecodeError, AttributeError):
            continue
    raise ValueError(
        f"no JSON move in response (stop_reason={resp.stop_reason}, "
        f"blocks={[b.type for b in resp.content]})"
    )
