# RTS backend (Anthropic overhaul)

The WordNet/BERT/nltk engine is gone. The brain is now a single Claude call per turn
with the rules of RTS burned into a cached system prompt, plus a thin layer of
deterministic code for the two things that must be 100% reliable: the **R/T/S letter
ban** and **duplicate detection**.

## Architecture

```
frontend (unchanged)
   │  POST /echo {message}
   ▼
server.py (Flask, thin)  ──►  engine.py
                                1. deterministic pre-checks (free, reliable):
                                     empty · starts with r/t/s · exact dup/variation
                                     → ruled without calling the model
                                2. otherwise → one Claude call (structured output):
                                     response_code, chosen_word, train_of_thought[][], response
                                3. deterministic post-check on the AI's own word
                                     (never r/t/s, never a dup) → one retry, else concede
                                4. update in-memory GameState, return the contract JSON
```

- **Model:** `claude-sonnet-4-6`, structured output via `output_config.format`,
  `thinking: disabled` + `effort: low` for snappy turns, system prompt cached with
  `cache_control`.
- **State:** a single in-memory `GameState` (chain, used words, last word). `/reset`
  clears it. Deliberately global — this is a local single-player toy.

## Frozen frontend contract (unchanged)

- `POST /echo {"message": str}` → `{response, train_of_thought: [[...]], response_code}`
- `POST /reset` → `{response, train_of_thought}`
- `response_code == "UNRELATED"` is the only code the UI treats specially (stamps a
  "?" on the player's bubble). Codes: `OK · UNRELATED · DUPLICATE · INVALID · CHAT ·
  CONCEDE · RTS` (+ `ERROR` on failure).

## Run locally

```bash
cd backend
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.example .env            # then put your ANTHROPIC_API_KEY in .env
./venv/bin/python server.py     # serves on :5000
```

On macOS, AirPlay Receiver usually occupies port 5000. Either disable it
(System Settings → General → AirDrop & Handoff → AirPlay Receiver), or run
`PORT=5001 ./venv/bin/python server.py` and point the frontend's dev `API_URL`
(`frontend/src/components/chat.tsx`) at `http://localhost:5001`.

## Tuning the brain

Everything that makes the AI good at RTS lives in `SYSTEM_PROMPT` in `engine.py` —
the rules, the "balanced" connection philosophy (human-but-defensible links),
competitive strategy (spring R/T/S traps), persona, and few-shot examples. Tune the
prompt, not the code.
