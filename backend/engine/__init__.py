"""RTS engine.

The public surface is two functions - server.py needs nothing else:

    engine.play(message, game_id=..., reverse=...)  -> contract dict
    engine.reset(game_id=..., reverse=...)          -> contract dict

Inside:

    config.py       every knob, read from env (which model, which provider)
    rules.py        the deterministic rules, incl. the reversible letter rule
    state.py        game state, keyed by id so multiplayer is a routing change
    prompts.py      loads prompts/*.md - no prompt text lives in Python
    schema.py       the structured move every provider must return
    providers/      the brains: anthropic, any OpenAI-compatible (local/OSS), stub
    contract.py     the frozen frontend payload shape
    turn.py         orchestration: pre-checks -> brain -> post-checks -> advance
"""

from .state import SOLO_ID
from .turn import play, play_stream, reset, timeout

__all__ = ["play", "play_stream", "reset", "timeout", "SOLO_ID"]
