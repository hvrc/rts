"""A brain with no network — for tests, offline dev, and CI.

Plays the first word from a small pool that satisfies the active letter rule and
hasn't been used yet. Dumb on purpose: it exists to prove the plumbing (including the
reversed rule), not to play well.
"""

from .base import Provider

_POOL = [
    "apple", "owl", "moon", "candle", "bridge", "ember", "garden", "kite",
    "river", "steam", "thunder", "storm", "raven", "temple", "silk",
]


class StubProvider(Provider):
    name = "stub"

    def move(self, system_prompt, messages, ctx):
        pick = next(
            (w for w in _POOL if ctx.rule.allows(w) and w not in ctx.used),
            "",
        )
        if not pick:
            return {"response_code": "CONCEDE", "chosen_word": "",
                    "train_of_thought": [], "response": "ok, you got me"}
        return {
            "response_code": "OK",
            "chosen_word": pick,
            "train_of_thought": [[pick]],
            "response": pick,
        }
