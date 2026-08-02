"""The provider interface.

A provider is a brain. It gets a rendered system prompt, the conversation so far as a
list of {"role", "content"} messages, and a read-only view of the game (`ctx`), and
returns a dict matching schema.MOVE_SCHEMA. That's the entire contract - the engine never
knows or cares which model answered.

`messages` is real history, not a summary of it, and the last entry carries the current
board plus what the human just said. Providers should pass it through as-is; flattening it
back into a single string throws away the context the bot needs to tell a reply from a
move.

`ctx` exists so a provider can see the active rule and the used words without the
engine having to reach inside it. Model-backed providers ignore it (everything they
need is already in the prompt); the stub uses it to play legally, and future providers
may want it too.

To add a brain: subclass Provider, implement move(), register it in __init__.py.
"""


class TurnContext:
    """What a provider is allowed to know about the game."""

    def __init__(self, rule, used, chain, last_word):
        self.rule = rule
        self.used = used
        self.chain = chain
        self.last_word = last_word


class Provider:
    name = "base"

    def move(self, system_prompt, messages, ctx):
        """Return a dict matching schema.MOVE_SCHEMA.

        Raise on failure - turn.py catches and degrades to the "?" bubble.
        """
        raise NotImplementedError

    def stream_move(self, system_prompt, messages, ctx, schema=None):
        """The same turn, yielded as it is generated.

        Yields `(kind, payload)` pairs:

            ("field", (name, value))  a top-level string field finished. The schema is
                                      ordered so the code and the words all land before
                                      `response` starts, which is what lets the engine
                                      decide whether a turn is legal before any of the
                                      reply has been shown.
            ("delta", text)           more of `response`.
            ("done", data)            the whole parsed move.

        The default implementation is the non-streaming call wearing a costume: one
        `done` and nothing else. That keeps every provider valid without forcing each
        one to implement streaming, and the engine treats a provider that never emits a
        delta as simply slower, not broken.
        """
        yield "done", self.move(system_prompt, messages, ctx)
