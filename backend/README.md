# RTS backend

A thin Flask app over an `engine` package. Deterministic code owns the rules that must
be 100% reliable (the letter rule, duplicates); a model owns everything judgment-shaped
(relatedness, banter, strategy, its own move).

## Layout

```
server.py              Flask. Two routes, no logic.
engine/
  __init__.py          the public surface: play(), reset()
  config.py            every knob, read from env - which provider, which model
  rules.py             the deterministic rules, incl. the reversible letter rule
  state.py             game state, keyed by id (multiplayer is a routing change)
  prompts.py           loads prompts/*.md
  prompts/
    system.md          the brain. natural language, no code. edit this to change how it plays.
    letter_rule.normal.md    r/t/s are banned
    letter_rule.reverse.md   r/t/s are the ONLY legal openers
  schema.py            the structured move every provider must return
  providers/           the brains
    base.py            the interface: move(system_prompt, user_message, ctx) -> dict
    anthropic_provider.py
    openai_provider.py OpenAI-compatible: Ollama, LM Studio, vLLM, llama.cpp, Groq, ...
    stub_provider.py   no network. tests and offline dev.
  contract.py          the frontend payload shape
  turn.py              orchestration: pre-checks -> brain -> post-checks -> advance
```

## The shape of a turn

```
1. deterministic pre-checks   letter rule, duplicates       (rules.py)
2. ask the brain              one structured call           (providers/)
3. deterministic post-checks  the AI must obey rules too    (rules.py)
                              one retry, else concede
4. advance the chain          (state.py), shape the reply   (contract.py)
```

Steps 1 and 3 exist because a model is not 100% reliable and those two rules must be.

## Changing how the AI plays

Edit `engine/prompts/system.md`. No Python involved. The files are re-read every turn,
so an edit takes effect on the next move without a restart.

## Changing the model

Config, not code.

```bash
# Anthropic (default)
RTS_PROVIDER=anthropic
RTS_MODEL=claude-haiku-4-5
ANTHROPIC_API_KEY=sk-ant-...

# Any OpenAI-compatible server - local or hosted
RTS_PROVIDER=openai
RTS_BASE_URL=http://localhost:11434/v1   # Ollama, LM Studio, vLLM, llama.cpp, Groq...
RTS_MODEL=llama3.1

# No network at all
RTS_PROVIDER=stub
```

To add a provider: subclass `Provider`, implement `move()`, add one line to the registry
in `providers/__init__.py`.

## The letter rule, and the reverser

`LetterRule` governs both directions from one object, so the two modes cannot drift:

- **normal** - a word may NOT start with r/t/s.
- **reversed** - a word may ONLY start with r/t/s.

The client owns the toggle (the "r" circle in the header) and sends `reverse` on every
request, so the frontend and backend can't disagree about which rule is in force.
Flipping mid-game keeps the chain - the new rule governs words from there on.

## API

```
POST /echo  {"message": str, "reverse": bool}
         -> {response, train_of_thought: [[...]], response_code}
POST /reset {"reverse": bool}
         -> {response, train_of_thought}
```

`response_code` is one of `OK · UNRELATED · DUPLICATE · INVALID · CHAT · CONCEDE · RTS`
(+ `ERROR`). The UI only treats `UNRELATED` specially (it stamps a "?" on the player's
bubble); everything else just displays `response`.

## Run locally

```bash
cd backend
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env            # then put your ANTHROPIC_API_KEY in .env
PORT=5001 ./venv/bin/python server.py
```

macOS AirPlay squats on port 5000, hence 5001 - which is what the frontend's dev
`API_URL` already points at.

Offline, with no key at all:

```bash
RTS_PROVIDER=stub PORT=5001 ./venv/bin/python server.py
```

## Known wart

The `cache_control` on the system prompt is a no-op today. The prompt is ~1.4k tokens and
Haiku 4.5 will not cache a prefix below 4096, so the API silently declines and every turn
pays full input price. It's left in place so it starts working if the prompt grows past
that floor.
