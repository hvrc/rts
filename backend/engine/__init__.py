"""RTS engine.

The public surface server.py needs:

    engine.play(message, game_id=..., reverse=...)  -> contract dict
    engine.reset(game_id=..., reverse=...)          -> contract dict
    engine.timeout(game_id=..., who=...)            -> contract dict
    engine.ROOMS / engine.roomturn                  -> the multiplayer side

Inside:

    config.py       every knob, read from env (which model, which provider)
    rules.py        the deterministic rules, incl. the reversible letter rule
    state.py        game state, keyed by id so multiplayer is a routing change
    prompts.py      loads prompts/*.md - no prompt text lives in Python
    schema.py       the structured move every provider must return
    providers/      the brains: anthropic, any OpenAI-compatible (local/OSS), stub
    contract.py     the frozen frontend payload shape
    turn.py         solo orchestration: pre-checks -> brain -> post-checks -> advance

    rooms.py        who is in a room, whose turn it is, and the room's clock
    roomturn.py     the same turn with more than two people taking it
    bus.py          fan a room's events out to every browser watching it
"""

from . import roomturn
from .rooms import ROOMS
from .state import SOLO_ID
from .turn import play, play_stream, reset, timeout

__all__ = ["play", "play_stream", "reset", "timeout", "SOLO_ID", "ROOMS", "roomturn"]
