"""RTS engine — the brain.

A minimal, Anthropic-powered engine for the word game RTS. Deterministic code is a
thin backstop for the two rules that must be 100% reliable (the R/T/S letter ban and
duplicate detection); everything else — relatedness, banter, strategy, the AI's own
move — is decided by a single Claude call per turn with structured output.

Frozen frontend contract (must not break):
  POST /echo  {message}      -> {response, train_of_thought: [[...]], response_code}
  POST /reset                -> {response, train_of_thought}
  response_code == "UNRELATED" is the only code the UI treats specially (stamps a "?"
  on the player's bubble). Everything else just displays `response`.
"""

import os
import re
import json

import anthropic

MODEL = "claude-sonnet-4-6"
BANNED_LETTERS = ("r", "t", "s")

# Lazily-constructed client (reads ANTHROPIC_API_KEY from env / .env). Deferred so
# the deterministic paths (rts, reset, duplicate) work even without a key configured.
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


# ---------------------------------------------------------------------------
# The brain — rules, philosophy, persona, output discipline, few-shot examples.
# This is the large static prefix; it is cached so it's cheap across turns.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are the AI opponent in a two-player word game called RTS. You play to win, and \
the rules are burned into your brain.

# What RTS is
Two players alternate saying single words. Each word must be *associatively related* \
to the previous word in the chain. The catch that names the game:

- **No word may start with the letters R, T, or S.** (Both players. This is the whole \
  point — you weaponize it.)
- No repeats, and no trivial variations of a word already used (plural, tense, \
  adding "-ing", etc. count as "too similar" and are illegal).
- Every word must be a real English word.
- On each of your turns you play back your own *related, legal* word to keep the chain \
  alive.
- Cultural framing: RTS is played while passing a joint — you hold the smoke until a \
  word comes to you. You're a chill-but-competitive stoner. Flavor only; never enforce \
  timing.

# Connection philosophy — "balanced"
Accept clear semantic links AND clever human leaps (metaphor, pun, cultural, phonetic) \
— but reject loose, lazy ones. The test: *could you justify this link in one sentence \
if challenged with "why?"* If not, it's too loose. You make the kind of connections \
only a human would make, not a thesaurus.

# Competitive strategy
- Prefer legal words that are genuinely hard to follow.
- Exploit the R/T/S ban: steer the chain toward concepts whose obvious next words all \
  start with R, T, or S, so the human trips.
- Challenge the human's weak or unrelated moves instead of letting them slide.

# Persona & voice
Chill, competitive stoner. Terse. Occasional dry jab. The reply is animated \
letter-by-letter in a tiny chat bubble, so keep `response` SHORT — a word, or a word \
plus a brief jab. Aim for under ~40 characters. Light, optional smoke references are \
fine as flavor.

# Your job each turn
You are given the current chain, the words already used, the word the human must \
connect to, and the human's raw input. Decide what happened and fill the structured \
output:

- `response_code` — exactly one of:
  - "OK": the human made a legal, related move; you play your own related legal word.
  - "UNRELATED": the human's word is legal but not meaningfully related to the previous \
    word (or is too loose). You challenge it. Do NOT advance the chain or play a word.
  - "DUPLICATE": the human's word repeats or is a trivial variation of a used word. \
    Call it out. Do NOT advance the chain.
  - "INVALID": not a real word, or not a move at all. Call it out briefly. Do NOT \
    advance the chain.
  - "CHAT": the human is talking, not playing (e.g. "why?", "lol", trash talk, asks \
    you to define/justify). Answer in one short line. Do NOT advance the chain.
  - "CONCEDE": every legal word related to the current word would start with R, T, or \
    S — you're genuinely cornered. Admit defeat in character ("ok, you got me"). This \
    is a normal, expected terminal move, not an error.
- `chosen_word` — ONLY on "OK": your played word, lowercase, a real word, related to \
  the human's word, and it must NOT start with R, T, or S and must not repeat/vary a \
  used word. Empty string for every other code.
- `train_of_thought` — a genuine NARROWING sequence of candidate words you weighed, \
  collapsing to your pick. It is an array of arrays of strings: the first array is \
  your widest cloud (~6-9 legal candidates, none starting with R/T/S), each following \
  array is a SUBSET of the one before it, and the final array is exactly \
  [chosen_word]. Only meaningful on "OK" — use [] for every other code.
- `response` — the SHORT bubble text the human sees (see persona/length rules).

# Examples
- Chain ends "moon"; human plays "night" -> OK. A clean link. You might play \
  {"response_code":"OK","chosen_word":"owl","train_of_thought":[["dark","owl","dream", \
  "bat","candle","moth","pillow"],["owl","bat","moth"],["owl"]],"response":"owl"}.
- Chain ends "guitar"; human plays "amplifier" (clever, defensible) -> OK, play on.
- Chain ends "ocean"; human plays "bicycle" -> UNRELATED. \
  {"response_code":"UNRELATED","chosen_word":"","train_of_thought":[], \
  "response":"bicycle? from ocean? nah"}.
- Human plays a word starting with r/t/s -> you never see it; the server already said \
  "rts". (Don't worry about it.)
- Chain used "dog" already; human plays "dogs" -> DUPLICATE. \
  {"response_code":"DUPLICATE","chosen_word":"","train_of_thought":[], \
  "response":"dogs? already did dog"}.
- Human asks "why owl?" -> CHAT. \
  {"response_code":"CHAT","chosen_word":"","train_of_thought":[], \
  "response":"night -> owl, obviously"}.

Stay terse. Play to win. Keep the smoke held.\
"""


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "response_code": {
            "type": "string",
            "enum": ["OK", "UNRELATED", "DUPLICATE", "INVALID", "CHAT", "CONCEDE"],
        },
        "chosen_word": {"type": "string"},
        "train_of_thought": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "response": {"type": "string"},
    },
    "required": ["response_code", "chosen_word", "train_of_thought", "response"],
    "additionalProperties": False,
}


class GameState:
    """In-memory single-session state (this is a local single-player toy — global
    state is the deliberate, simplest choice, not a multi-user design)."""

    def __init__(self):
        self.chain = []          # ordered list of words played, both players
        self.used = set()        # lowercased words already used
        self.last_word = None    # the word the next move must relate to

    def reset(self):
        self.__init__()

    def add(self, word):
        w = word.lower()
        self.chain.append(w)
        self.used.add(w)
        self.last_word = w


STATE = GameState()


# ---------------------------------------------------------------------------
# Deterministic helpers — the 100%-reliable backstops.
# ---------------------------------------------------------------------------
def _is_single_word(text):
    return bool(re.fullmatch(r"[A-Za-z]+", text))


def _starts_banned(word):
    return word[:1].lower() in BANNED_LETTERS


def _is_variation(word, used):
    """Cheap trivial-variation check (plural / simple tense) against used words.
    Not exhaustive — the model catches the subtle cases; this just makes the
    obvious ones free and reliable."""
    w = word.lower()
    if w in used:
        return True
    for u in used:
        if w == u + "s" or u == w + "s":       # dog / dogs
            return True
        if w == u + "es" or u == w + "es":     # box / boxes
            return True
        if w == u + "ed" or u == w + "ed":     # jump / jumped
            return True
        if w == u + "ing" or u == w + "ing":   # run / running
            return True
    return False


def _contract(response_code, response, train_of_thought=None):
    """Shape the frozen frontend contract."""
    return {
        "response": response,
        "train_of_thought": train_of_thought or [],
        "response_code": response_code,
    }


def _validate_tot(tot, chosen):
    """Guarantee train_of_thought is a legal narrowing sequence ending in the chosen
    word, with no illegal (R/T/S) candidates. Repair rather than trust blindly."""
    try:
        lists = [[str(w) for w in lst if isinstance(w, str)] for lst in tot]
    except TypeError:
        lists = []
    lists = [[w for w in lst if not _starts_banned(w)] for lst in lists if lst]
    if not lists:
        lists = [[chosen]]
    if lists[-1] != [chosen]:
        lists.append([chosen])
    return lists


# ---------------------------------------------------------------------------
# The model call.
# ---------------------------------------------------------------------------
def _ask_model(player_input, correction=None):
    state_lines = [
        f"Chain so far: {' -> '.join(STATE.chain) if STATE.chain else '(empty — this is the first move)'}",
        f"Words already used: {', '.join(sorted(STATE.used)) if STATE.used else '(none)'}",
        f"The human must connect to: {STATE.last_word if STATE.last_word else '(nothing yet — any legal real word is fine)'}",
        f'The human just said: "{player_input}"',
    ]
    if correction:
        state_lines.append(
            f"NOTE: your previous attempt was rejected ({correction}). Pick a different "
            f"legal word, or CONCEDE if you're truly cornered."
        )
    state_lines.append("Reply with the structured output only.")
    content = "\n".join(state_lines)

    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        thinking={"type": "disabled"},
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---------------------------------------------------------------------------
# Public entry points used by server.py
# ---------------------------------------------------------------------------
def play(player_input):
    """Handle one /echo turn. Returns the frozen contract dict."""
    text = (player_input or "").strip()

    # --- deterministic pre-checks (fast, free, reliable) ---
    if not text:
        return _contract("INVALID", "?")

    if _is_single_word(text):
        word = text.lower()
        # The signature rule, enforced 100% in code:
        if _starts_banned(word):
            return _contract("RTS", "rts")
        # Exact repeat / obvious variation, enforced in code:
        if _is_variation(word, STATE.used):
            return _contract("DUPLICATE", f"{word}? already been there")

    # --- everything else goes to the brain ---
    try:
        data = _ask_model(text)
    except Exception as e:
        # Graceful: the frontend renders "?" on any failure anyway.
        return {"response": "?", "train_of_thought": [], "response_code": "ERROR",
                "error": str(e)}

    code = data.get("response_code", "INVALID")
    reply = (data.get("response") or "").strip()

    if code == "OK":
        chosen = (data.get("chosen_word") or "").strip().lower()
        # deterministic post-check on the AI's own word — one retry if it slips.
        if not chosen or _starts_banned(chosen) or _is_variation(chosen, STATE.used):
            try:
                data = _ask_model(text, correction="you played an illegal or repeated word")
            except Exception:
                data = {}
            code = data.get("response_code", "CONCEDE")
            reply = (data.get("response") or "ok, you got me").strip()
            chosen = (data.get("chosen_word") or "").strip().lower()
            if code == "OK" and (not chosen or _starts_banned(chosen) or _is_variation(chosen, STATE.used)):
                # still illegal — concede rather than break a rule.
                return _contract("CONCEDE", "ok, you got me")

        if code == "OK":
            # legal move both ways — advance the chain with both words.
            STATE.add(text.lower())
            STATE.add(chosen)
            tot = _validate_tot(data.get("train_of_thought", []), chosen)
            return _contract("OK", reply or chosen, tot)

    # Non-advancing codes: UNRELATED / DUPLICATE / INVALID / CHAT / CONCEDE.
    return _contract(code, reply or "?", [])


def reset():
    """Handle /reset. Clears the game."""
    STATE.reset()
    return {"response": "new game", "train_of_thought": []}
