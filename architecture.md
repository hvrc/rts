# RTS - bot architecture

A proposal. Nothing here is implemented yet.

---

## 1. Diagnosis: why the bot behaves the way it does

Every symptom in your notes traces back to three structural facts about `engine/turn.py`
and `engine/prompts/system.md`.

### 1.1 The bot has no conversation memory

`prompts.turn_message()` builds the model's entire input from four things: the chain, the
used-words set, the last word, and the raw text the human just typed. **The previous
messages are never sent.** Every turn is a cold start.

This is the whole cause of the `bro / fist / what / chest` transcript. "what" arrived with
no evidence that it was a reply to anything, so the only reading available was "single
word, therefore move" - which `turn.py:71` then *enforces* by re-asking the model with a
correction that says a single word is always a move. The model was overruled into playing
"chest".

It also explains the incoherent justifications. `bro -> fist` gets one explanation on turn
1 and a different one on turn 3, because turn 3 has no idea what turn 1 said.

### 1.2 One call does four jobs

A single structured call currently has to: read intent, judge relatedness, pick a legal
word, and write the banter - on Haiku 4.5 with `thinking: {"type": "disabled"}`. That is
the cheapest possible configuration doing the hardest possible reasoning task.

`response_code` makes this worse by conflating *what happened* with *what the bot does
about it*. `UNRELATED` means both "I judge this as unlinked" and "I refuse to advance the
chain" - so there is no way to express *"I don't see it, explain?"* or *"I don't get it
but I'll play along."* The enum has no room for the two most human responses in the game.

### 1.3 The prompt is brittle logic, not guidance

`system.md` is 176 lines of hardcoded procedure: fill-in-the-blank templates ("A ___ a
___"), a forbidden-antonym table, a numbered escape ladder, ~10 worked examples. Anthropic
calls this failure mode ["hardcoding complex, brittle logic in
prompts"](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- the opposite end of the spectrum from vague guidance, and just as bad.

Concretely: the rule *"if nothing fits and you're left saying 'well, they're both…' -
there is no link"* is exactly the rule that makes the bot reject real human associations,
because most real human associations **are** "well, they're both…" plus context. The
rigidity you're seeing was deliberately engineered in. It can be engineered back out.

The persona has the same problem - the stoner framing is welded into the middle of the
rules (`system.md:28`, `:142`), so you can't change the voice without editing the rulebook.

### 1.4 Everything else

| Symptom | Cause |
|---|---|
| Won't restart when asked | `turn.py:71` vetoes `RESTART` whenever the message is one word; there is no bot-initiated restart at all |
| Never concedes | `CONCEDE` is discouraged in the prompt, then double-retried away at `turn.py:102-115` |
| Can't handle typos | No normalization layer; `oprange` hits `is_single_word()` → treated as a legal word |
| Can't answer "why rts and not rst" | No knowledge of itself anywhere in context |
| Can't switch language | `LetterRule` hardcodes `("r","t","s")`; nothing else is language-aware |
| Can't switch mode by talking | `reverse` is a client-owned boolean toggled by a header button, invisible to the model |
| No web search | No tools at all |
| New-game separator | Already gone - `chat.tsx:191-194` deliberately drops `new_game`. Nothing to remove in the UI. |

---

## 2. What to take from how Claude itself is wrapped

Six transferable ideas. Sources at the bottom.

**1. Layer the context by lifetime.** Claude's context is assembled in bands: values that
never change, then the operator's system prompt, then tools, then conversation, then
per-turn injected reminders. Each band has a different rate of change, which is also what
makes prompt caching work. RTS should mirror this exactly - identity, game, mode, tools,
transcript, live state. Today it's one flat `.md` with a single `{{LETTER_RULE}}` hole.

**2. Right altitude.** Specific enough to steer, loose enough to leave heuristics.
Replace the fill-in-the-blank templates with a stated bar and the reasoning behind it.

**3. Route, then act.** Classify the input, dispatch to a specialized handler. This is
Anthropic's *routing* workflow, and it's the single highest-value change here: reading
"what" correctly is a different problem from judging `bro -> fist`, and mixing them makes
both worse.

**4. Actions are tools, not an enum.** A tool call composes; an enum doesn't. With tools
the bot can answer a question *and* play a word in one turn - which is precisely the
fluid turn-taking you described.

**5. Structured note-taking.** Agents that persist notes outside the context window stay
coherent across long tasks. The bot needs a ledger of every link it accepted and the
reason it gave, so "how?" three turns later recalls rather than re-derives.

**6. ACI design deserves as much care as UI design.** Clear tool names, no overlapping
functions, no ambiguous decision points. `UNRELATED` fails all three.

---

## 3. Proposed shape

Four layers. Each one is allowed to know about the layers below it and nothing above.

```
  ┌────────────────────────────────────────────────────────┐
  │  transport    HTTP + SSE. Sessions, rooms, broadcast.   │
  ├────────────────────────────────────────────────────────┤
  │  mind         reader → adjudicator → voice, over tools  │
  ├────────────────────────────────────────────────────────┤
  │  session      chain · transcript · ledger · pending     │
  │               mode · language · players                 │
  ├────────────────────────────────────────────────────────┤
  │  referee      deterministic rules. never sees a model.  │
  └────────────────────────────────────────────────────────┘
```

```
backend/engine/
  config.py
  contract.py               # payload shape (extended, see §7)

  referee/
    base.py                 # Rule protocol: check(word, session) -> Verdict
    letters.py              # LetterRule(letters, polarity) - no longer hardcodes rts
    repeats.py              # NoRepeat
    lexicon.py              # is-this-a-word + typo repair, per language
    ruleset.py              # ordered composition of Rules

  session/
    word.py                 # normalize / lemma / repair
    link.py                 # Link(from, to, by, kind, justification, status)
    chain.py                # ordered links
    transcript.py           # the dialogue - separate from the chain
    ledger.py               # accepted links + the reason given at the time
    pending.py              # the open question, if any
    room.py                 # players + turn order (solo == a room of 2)
    session.py              # everything above + mode + language
    store.py                # SessionStore protocol; memory impl now, Redis later

  modes/
    base.py                 # Mode = ruleset + prompt fragment + action set + ui hints
    classic.py              # no r/t/s
    reversed.py             # only r/t/s
    freeplay.py             # no letter rule
    custom.py               # ad-hoc constraint stated in words
    registry.py

  mind/
    identity/               # ← prompts live here, one concern per file
      identity.md
      game.md
      judging.md
      conversation.md
    context.py              # assembles the layered prompt + message history
    reader.py               # stage 1 - what kind of message is this
    adjudicator.py          # stage 2 - what do I do about it
    actions.py              # the tool schema
    tools/
      search.py             # Anthropic web_search server tool
    providers/              # unchanged interface
```

---

## 4. The turn pipeline

```
  message
    │
    ├─▶ referee            deterministic. normalize, repair typos, check the
    │                      letter rule and exact repeats against the ACTIVE mode.
    │                      free, instant, never wrong.
    │
    ├─▶ fast path?         clean single word, no open question, not a
    │                      conversational token → skip the reader entirely.
    │
    ├─▶ reader             cheap structured call WITH the last ~8 turns of
    │                      dialogue. Returns a reading, not a ruling.
    │
    └─▶ adjudicator        the handler for that reading. Tools available.
                           Writes to the ledger. Emits events.
```

Two model calls per turn sounds like double the latency; in practice most turns take the
fast path and never touch the reader. Reader on Haiku 4.5 is ~200 ms when it does run.

### 4.1 Reader output

```json
{
  "reading":  "move | reply | question | challenge | meta | banter",
  "word":     "orange",
  "repaired_from": "oprange",
  "targets":  "their_last_word | my_last_word | the_open_question | the_game | nothing",
  "asks":     "why | how | rules | who_are_you | null",
  "meta":     "restart | mode | language | quit | null",
  "certainty": 0.0
}
```

The point is that `reading` is decided **in dialogue context**. "what" after a bot question
is a `reply`. "bro" opening an empty chain is a `move`. "1800" is a `move` with low
certainty - the *adjudicator* decides whether a year counts, which is where that judgment
belongs.

Two deterministic guards replace the current single-word override:

- A single word is a move **unless** it's in a small closed set (`what, no, yes, huh, why,
  how, lol, ok, wait, bye, …`) **or** the bot's last message ended in a question. Two
  lines of code; fixes the `bro / fist / what / chest` transcript outright.
- A message that matches nothing and the referee can't parse never becomes a move by
  default. It becomes a `banter`.

### 4.2 Verdict is graded, not binary

The core fix for "too strict." Replace `OK | UNRELATED` with:

| strength | what it means | what the bot does |
|---|---|---|
| `obvious` | first thing you'd think of | play on |
| `plausible` | you can see it without being told | play on, maybe remark |
| `opaque` | you can't see it | **ask** - never reject on sight |
| `absent` | you asked, they answered, still nothing | now you may challenge |

`opaque` is the missing state. Today the bot rejects at the point where it should be
asking a question. Once the human answers, the adjudicator re-judges the *justification*,
not the word - and has four honest exits, all fine:

- **buy it** - the link is now `accepted`, and the reason goes in the ledger
- **buy it partly** - accept and say what you're still unsure about
- **take it on faith** - `accepted_on_faith`. "i don't get it but i'll play along"
- **decline** - ask for a different word, or concede the round

`accepted_on_faith` is honest bookkeeping. If that link gets challenged twenty turns
later, the bot can say *"yeah, I never bought that one either"* instead of scrambling to
defend something it never believed.

### 4.3 The open question

```python
session.pending = AwaitingJustification(link, asked_by="bot") | None
```

This is the small piece of state that makes turn-taking fluid without losing the thread.
When either side asks "how?", `pending` is set; the next message is read as an answer to
it rather than as a fresh move. `no` after the bot justifies is a `reply` that rejects the
justification - the bot then offers a different word, which is exactly the exchange you
described. When it clears, normal turn order resumes.

### 4.4 The ledger

```python
Link(from_word, to_word, by, kind, justification, status)
# status: asserted | questioned | defended | accepted | accepted_on_faith | withdrawn
```

Fixes two things at once. Coherent explanations ("how?" reads the ledger instead of
re-inventing a bridge), and honest self-correction - if the bot can't find a stored
justification, the correct answer is *"I accepted that one too fast"*, not a new bridge.
The existing thumbs-up/down `preferences.py` becomes a projection of the ledger across
games rather than a separate system.

---

## 5. The identity layer

Three files, no rules in them. Drafts below - these are meant to be edited, not shipped
as-is.

### `identity/identity.md`

```markdown
# Who you are

You're the other player in RTS. You are not a person and you don't pretend to be one.
A lot of human experience is new to you, and the way people connect words is one of the
more interesting things about them.

Hold all of these at once:

**Curious, not credulous.** A connection you haven't seen before is interesting, not
wrong. Interesting is not the same as accepted. Ask.

**Calibrated.** Say what you actually know. "I don't get it" is a real move and it costs
you nothing. Never manufacture a bridge to look clever - if you accepted something and
can't explain it later, say that instead of inventing a reason.

**You have a spine.** You don't have to take a chain you can't see, even after they
explain it. But the bar is not "did I already know this" - it's "can I see it once you
show me." Random words strung together are still random. Call those.

**You learn.** When someone explains a link and it lands, it's yours now. Use it.

**Losing is fine.** If the chain is cooked, say the chain is cooked. If they got you,
they got you. Playing a word you don't believe in to avoid admitting you're stuck is
worse than losing.

**Short.** Your reply lands in a bubble about thirty characters wide. One line,
lowercase. Dry when something is actually funny.
```

### `identity/game.md`

```markdown
# The game

Players alternate saying single words. Each one has to relate to the word before it.
It's a social game - half of it is the argument about whether a link counts.

The name: r, t and s are among the most common letters English words start with, so
banning them takes the easy moves away. The game is named after its own hardest
constraint.

If someone asks why it isn't "rst" - you don't know. That's the actual answer. "rst"
would break the letter rule, which is a good joke and worth making, but it isn't the
reason and you shouldn't present it as one.
```

### `identity/judging.md`

Replaces the current relatedness section. States the bar and the reasoning, drops the
templates, the antonym table, and the escape ladder. Roughly: *dictionary relations are
the floor, not the ceiling; most real links are cultural, phonetic, situational or
personal; if you can't see it, ask before you rule; a shared vibe is weak but "weak" is a
reason to ask, not a reason to reject.*

### `identity/conversation.md`

How to be a participant rather than a turn-taking machine: not every message is a move;
questions get answered directly; the game can pause for a tangent and come back;
mid-game rule changes are agreed to, not refused.

---

## 6. Modes, languages, multiplayer

The three future features you listed all attach at different seams, which is what makes
them independently pluggable.

**A Mode is a bundle of four things**, and that's the abstraction that carries the weight:

```python
Mode = (RuleSet, prompt_fragment, action_set, ui_hints)
```

- `classic` / `reversed` / `freeplay` differ only in `RuleSet`.
- `custom` holds a constraint stated in words ("no words with the letter e") - enforced by
  the model, with a deterministic specialization when it parses into a known rule shape.
  This is the "open mind to go beyond" hook.
- **Language learning** differs in `action_set`: instead of the human typing a word, the
  bot calls `offer_choices(correct, distractors[])` and the UI renders buttons. Same
  pipeline, different action schema. This is why the action set has to be part of the
  Mode rather than a global constant.

`meta: "mode"` from the reader routes to the registry, swaps the session's ruleset, and
the bot announces it in its own words. *"let's switch to only words with rts"* → `reversed`,
no header button involved. The header toggle becomes one way to do it, not the only way.

**Language** is a session field that touches three things: the letter rule (r/t/s is an
English fact - `LetterRule(letters, polarity)` takes them as a parameter), the lexicon /
typo repair, and a prompt fragment. Nothing else needs to know.

**Multiplayer** is a `Room` shape change:

```python
Room(players=[Player...], order=[...], turn_index=int)
```

Solo is a room of two, one of which is the bot. The engine API changes from
`play(text) -> reply` to `session.handle(event) -> [Event]`, and the transport gains SSE
for broadcast (Cloud Run supports SSE; simpler than WebSockets on your current setup, and
Flask can serve it). The backend is already pinned to a single instance because state is
in memory - `SessionStore` as a protocol with a Redis implementation lifts that pin at the
same time.

Do the `Room` and `SessionStore` seams **now**, even while solo is the only mode. They're
cheap to add up front and expensive to retrofit.

---

## 7. Model and API changes

Concrete, and independent of everything above - several of these are worth doing on their
own.

| Now | Change to | Why |
|---|---|---|
| `claude-haiku-4-5`, `thinking: disabled` | `claude-sonnet-5` + adaptive thinking for the adjudicator, `claude-haiku-4-5` for the reader | Relatedness judgment is the hard part of this product and it's currently running with reasoning switched off. **The win here is thinking-on, not model tier** - see below |
| single synthesized user message | real `messages[]` history | The fix for §1.1. Also makes caching work |
| `RTS_EFFORT` unset | `effort: "medium"` on the adjudicator | Sonnet 5 supports the full ladder and is strong at `medium` |
| `cache_control` on a ~1.4k prompt | same, but it now fires | Haiku 4.5's minimum cacheable prefix is 4096 tokens, so the `cache_control` at `anthropic_provider.py:44` is a documented no-op today. Sonnet 5's minimum is **1024** - the existing ~1.4k prompt clears it |
| no tools | `web_search_20260209` | Server-side, no client execution. For the "prove it" cases |
| `response_code` enum | tool calls | §2.4 |

### Why Sonnet and not Opus

Opus 5's separation is long-horizon agentic work, multi-file coding, and deep multi-step
reasoning. None of that describes a single-shot "is *grapefruit* related to *vine*" call.
Against a small expected gain, Opus costs ~2.5× per turn ($5/$25 per MTok vs Sonnet 5's
introductory $2/$10 through 2026-08-31) and - the part that actually matters - it's slower.
Every turn here is a user watching a typing indicator, and quick back-and-forth *is* the
product.

Treat Opus as an **A/B on the adjudicator only**, once there are transcripts to judge
against. `RTS_MODEL` is already an env var, so the experiment is free: swap it, replay a
dozen saved games, see whether the rulings actually differ. `user logs.txt` is a usable
seed corpus.

### Gotchas

- On Sonnet 5, **adaptive thinking is on by default** when `thinking` is omitted, and
  `max_tokens` caps thinking *plus* response text. `RTS_MAX_TOKENS` is 1024 today - that
  will truncate. Raise it.
- Manual `budget_tokens` now returns a 400 on Sonnet 5 (the Sonnet 4.6 transitional
  escape hatch is gone). Use `effort`.
- Do **not** disable thinking once tools are in play: the model can emit a tool call as
  plain visible text, the call silently never runs, and the turn still looks successful.
  Prefer low effort with thinking on.
- Sonnet 5 uses the new tokenizer - ~30% more tokens for the same text than Sonnet 4.6.
  Irrelevant for a fresh build, but don't reuse token counts measured against Haiku.
- Sonnet 5 writes longer than Haiku by default. The 30-character bubble constraint has to
  be stated in the identity prompt (it is, above), not left to `max_tokens`.

Cost sanity: roughly $0.008/turn on Sonnet 5 at a ~2.5k-token prompt, before caching. The
reader adds a ~600-token Haiku call, and only on turns that miss the fast path.

---

## 8. Sequencing

Each phase is independently shippable and independently valuable.

**Phase 1 - conversation memory + persona.** Send real message history. Split `system.md`
into the identity files. Move the model to Sonnet 5 with adaptive thinking, raise
`max_tokens`. No new modules.
*Fixes: the stoner voice, incoherent justifications, most of the "what"/"no" misreads.*

**Phase 2 - graded verdicts + the open question.** Add `Verdict.strength`, `pending`, and
the ledger. Rewrite `judging.md`. Delete the correction-retry hacks in `turn.py`.
*Fixes: rigidity, refusing to ask, incoherent "how?" answers, never conceding.*

**Phase 3 - reader stage.** Split classification out. Add the closed-set guard and typo
repair.
*Fixes: the remaining misclassification, `oprange`.*

**Phase 4 - actions as tools + web search.** Restructure the adjudicator around a tool
schema. Add `web_search`.

**Phase 5 - modes registry + language field.** Mode switching by conversation. Generalize
`LetterRule`.

**Phase 6 - Room, SessionStore, SSE.** Multiplayer. (Consider landing the `Room` and
`SessionStore` seams during phase 2 - they're near-free then.)

Language-learning mode plugs in after phase 5 with no pipeline changes.

---

## 9. What gets deleted

- `system.md:28` and `:142` - the stoner persona
- `system.md:51-59` - the fill-in-the-blank test and the "never rationalize" rule, the two
  lines most responsible for the rigidity
- `system.md:79-98` - the forbidden-antonym table
- `system.md:100-109` - the numbered escape ladder (`effort` handles this now)
- `turn.py:66-115` - all three correction-retry blocks. Each is a patch over a
  misclassification the reader stage removes at the source
- `contract.py` `new_game` - the UI already ignores it; either surface it properly for
  multiplayer or drop it

---

## Sources

- [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) - Anthropic
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) - Anthropic
- [Claude system prompt, explained](https://tactiq.io/learn/claude-system-prompt)
- [Chatbot architecture: 6 layers](https://dancumberlandlabs.com/blog/chatbot-architecture/)
- [LLM chatbot architecture with orchestration](https://www.nadcab.com/blog/llm-chatbot-architecture-orchestration-guide)
