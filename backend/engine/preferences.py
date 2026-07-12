"""Learned taste — which kinds of links the human likes.

A preference is a link: `from -> to`, the pair the AI played. Thumbs-up on a bot word
means "more leaps like that"; thumbs-down means "fewer".

The client owns this. It stores the pairs (localStorage) and sends them on every turn,
so taste survives instance recycles, deploys, and a wiped backend, and it stays private
to that browser. The engine only formats them into the prompt — it never persists
anything.

Capped, because this rides in the prompt on every single turn and an unbounded list
would quietly grow the bill.
"""

MAX_PER_LIST = 30


class Preferences:
    def __init__(self, liked=None, disliked=None):
        self.liked = _clean(liked)
        self.disliked = _clean(disliked)

    @classmethod
    def from_payload(cls, payload):
        """Build from whatever the client sent. Trusts nothing."""
        data = payload if isinstance(payload, dict) else {}
        return cls(liked=data.get("liked"), disliked=data.get("disliked"))

    def is_empty(self):
        return not self.liked and not self.disliked

    def as_prompt_block(self):
        """The lines spliced into the turn message. Empty string when there's no taste
        to report, so a fresh player costs nothing."""
        if self.is_empty():
            return ""
        parts = []
        if self.liked:
            parts.append(
                "Links this human LIKED (they enjoy this kind of leap — prefer moves "
                "of this shape when one is legal):\n"
                + "\n".join(f"  - {a} -> {b}" for a, b in self.liked)
            )
        if self.disliked:
            parts.append(
                "Links this human DISLIKED (avoid moves of this shape):\n"
                + "\n".join(f"  - {a} -> {b}" for a, b in self.disliked)
            )
        return "\n".join(parts)


def _clean(pairs):
    """Keep only well-formed [from, to] string pairs, lowercased and deduped."""
    out = []
    seen = set()
    for pair in (pairs or [])[-MAX_PER_LIST * 2:]:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        a, b = pair
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        a, b = a.strip().lower(), b.strip().lower()
        if not a or not b or (a, b) in seen:
            continue
        seen.add((a, b))
        out.append((a, b))
    return out[-MAX_PER_LIST:]
