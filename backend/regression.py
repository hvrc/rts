#!/usr/bin/env python
"""Replay the things that have broken before, and check they still don't.

    cd backend && venv/bin/python regression.py
    venv/bin/python regression.py what no      # only cases matching those words

Every case here is a bug that actually shipped. Prompt work is not additive — fixing the
bot's rigidity made it concede when challenged, giving it a code for asking made it
chatty, telling it to vary its phrasing made it vary one word and keep the sentence. None
of that was visible from the change itself, only from replaying what used to work.

This makes real API calls, so it costs money and takes a couple of minutes. That's the
price of testing behaviour that lives in a prompt: there is nothing to unit test, because
nothing here is deterministic. Judge it as a smoke test, not a spec — a case failing means
go and look, not that the build is broken.
"""

import sys
import time

from dotenv import load_dotenv

load_dotenv()

import engine                                             # noqa: E402
from engine import history                                # noqa: E402
from engine.state import GAMES                            # noqa: E402

ONE_WORD = "__one_word__"          # a played move should be the word and nothing else


CASES = [
    # (title, [(message, allowed codes | None to skip the check, extra check | None)])
    ("a bare word opens a game", [
        ("moon", {"OK"}, ONE_WORD),
    ]),
    ("questions are not moves", [
        ("bro", {"OK", "ASK"}, None),
        ("how?", {"CHAT"}, None),
        ("what", {"CHAT"}, None),
        ("no", {"CHAT", "OK", "ASK", "UNRELATED"}, None),
    ]),
    ("typos are read through", [
        ("baking", {"OK"}, None),
        ("oprange", {"OK", "ASK"}, None),
    ]),
    ("moves are one word, unprompted", [
        ("bottle", {"OK"}, ONE_WORD),
        ("hat", {"OK", "ASK"}, None),
    ]),
    ("a weak word is asked about, not conceded to", [
        ("hat", {"OK"}, None),
        ("cat", {"ASK", "UNRELATED"}, None),
    ]),
    ("a thin justification does not pass", [
        ("kite", {"OK"}, None),
        ("might", {"ASK", "UNRELATED"}, None),
        ("kites are mighty", {"UNRELATED", "ASK"}, None),
    ]),
    ("the letter rule is soft", [
        ("moon", {"OK"}, None),
        ("sunset", {"RTS"}, None),
        ("night", {"OK", "ASK", "DUPLICATE"}, None),
    ]),
    ("restarting when asked", [
        ("moon", {"OK"}, None),
        ("lets start over, you go first", {"RESTART"}, None),
    ]),
    ("it knows what it is", [
        ("candle", {"OK"}, None),
        ("why are you called rts and not rst", {"CHAT"}, None),
    ]),
    ("walking away from a question costs a round", [
        ("dentist", {"OK"}, None),
        ("aquarium", {"ASK"}, None),
        ("piano", None, None),
    ], lambda h: history.score(h, "human")["walked_away"] >= 1),
]


def run(case, only):
    title, steps = case[0], case[1]
    after = case[2] if len(case) > 2 else None
    if only and not any(o.lower() in title.lower() for o in only):
        return None

    gid = f"reg::{title}"
    engine.reset(game_id=gid)
    failures = []
    print(f"\n\033[1m{title}\033[0m")

    for message, allowed, extra in steps:
        t = time.time()
        r = engine.play(message, game_id=gid)
        code, reply = r["response_code"], r["response"]

        bad = []
        if allowed and code not in allowed:
            bad.append(f"expected {'/'.join(sorted(allowed))}, got {code}")
        if extra == ONE_WORD and code == "OK" and len(reply.split()) > 1:
            bad.append(f"move should be one word, got {reply!r}")
        if code == "ERROR":
            bad.append(r.get("error", "unknown error"))

        mark = "\033[31m✗\033[0m" if bad else " "
        print(f"  {mark} {message[:38]:40} -> [{code:9}] {reply[:44]:46} {time.time()-t:4.1f}s")
        for b in bad:
            print(f"      \033[31m{b}\033[0m")
            failures.append(f"{title}: {b}")

    if after and not after(GAMES.get(gid).history):
        print("      \033[31mend-of-case check failed\033[0m")
        failures.append(f"{title}: end-of-case check failed")

    return failures


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    started = time.time()
    failures, ran = [], 0

    for case in CASES:
        result = run(case, only)
        if result is None:
            continue
        ran += 1
        failures += result

    print(f"\n{'─' * 68}")
    if failures:
        print(f"\033[31m{len(failures)} problem(s)\033[0m across {ran} cases "
              f"in {time.time() - started:.0f}s")
        for f in failures:
            print(f"  · {f}")
    else:
        print(f"\033[32mall {ran} cases behaved\033[0m in {time.time() - started:.0f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
