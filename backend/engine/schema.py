"""The structured output every provider must return.

This is the contract between the engine and whatever brain is plugged in. A provider's
only job is to return a dict matching MOVE_SCHEMA - how it gets there (Anthropic
structured outputs, an OpenAI-compatible json_schema, a local model coaxed with a
json_object hint) is the provider's problem, not the engine's.

**Field order is load-bearing.** Structured outputs are emitted in schema order, so the
order here is the order the tokens arrive in, and that decides how a streamed turn feels:

  1. response_code, their_word, chosen_word   tiny, and everything the engine needs to
                                              decide whether this turn is legal
  2. response                                 the only part a human reads
  3. train_of_thought                         the largest field, and the one nobody sees
                                              unless the `s` toggle is on

Which means the deterministic post-checks can run before a single character of the reply
is shown - the engine knows the word by then - and the reply can stream the moment it
starts. `train_of_thought` used to sit above `response`, so every turn generated ~100
tokens of animation data before writing anything the player would read.
"""


def move_schema(with_train_of_thought=True):
    """The schema for this turn.

    The train of thought is only rendered when the `s` toggle is on, so when it's off it
    is generated and thrown away - the single largest slice of output tokens on the turn.
    Dropping it from the schema is a real latency saving, not a cosmetic one.
    """
    if with_train_of_thought:
        return MOVE_SCHEMA
    return _MOVE_SCHEMA_NO_TOT


MOVE_SCHEMA = {
    "type": "object",
    "properties": {
        "response_code": {
            "type": "string",
            "enum": ["OK", "ASK", "UNRELATED", "DUPLICATE", "INVALID", "CHAT", "CONCEDE",
                     "RESTART"],
            "description": (
                "OK - they played a word you accept; you play yours back.\n"
                "ASK - their word doesn't land for you and you want to hear why. Nobody "
                "loses, the chain waits. This is the right code whenever a link is "
                "unclear, and it is always better than guessing.\n"
                "UNRELATED - you asked, they answered, and it still does not connect. A "
                "challenge to them, not a loss for you.\n"
                "DUPLICATE - that exact word, or a plural or tense of it, is already in "
                "the chain.\n"
                "INVALID - not a word at all. Gibberish. Not merely a word you don't "
                "know, and not a typo you can read through.\n"
                "CHAT - they are talking, not playing: a question, an answer to yours, an "
                "argument, a joke, an aside. Answer it. The chain does not move.\n"
                "CONCEDE - YOU are stuck: every word you can think of is already used or "
                "breaks the letter rule, and you are giving them the round. This is "
                "ONLY ever about your own inability to find a word. It is never a "
                "response to a word of theirs you dislike (that is ASK or UNRELATED) and "
                "never a response to a question (that is CHAT). If they played something "
                "weak, they are the one in trouble - do not hand them the win for it.\n"
                "RESTART - they asked for a new game or asked you to open."
            ),
        },
        # The word the bot understood them to have played, normalised - "orange" from
        # "oprange", "war" from "jeez ok - war". Empty when they didn't play one.
        #
        # The engine used to append their raw message to the chain instead, which meant a
        # conversational turn the model answered with a word ("no" -> "pound") put "no"
        # in the chain as though it were a move. It also left typo repair nowhere to go:
        # the misspelling went into the chain and the correction came back as the bot's
        # own word.
        "their_word": {
            "type": "string",
            "description": (
                "The word they played, lowercased and corrected: 'orange' for a typed "
                "'oprange', 'war' for 'jeez ok - war'. Empty string if they did not play "
                "a word this turn - a question, an answer, an argument or a joke is not "
                "a move. This is what goes into the chain, so never put a whole phrase "
                "here."
            ),
        },
        "chosen_word": {"type": "string"},
        "response": {
            "type": "string",
            "description": (
                "What they see. When you play a word this is normally just that word on "
                "its own - no explanation of why it connects, no commentary. Only expand "
                "when they actually asked you something, and keep it to one short "
                "lowercase line even then."
            ),
        },
        "train_of_thought": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
            "description": (
                "Single words only - never sentences, reasoning or explanation. These are "
                "drawn scattered across the screen and then faded out one by one, so each "
                "string has to be one word a player might actually have played. A "
                "narrowing sequence: the first list is the wide field of candidates you "
                "weighed (6-9 words, all legal, none already used), each list after it "
                "drops some of them, and the last is exactly [chosen_word]. Empty when "
                "you didn't play a word."
            ),
        },
    },
    "required": ["response_code", "their_word", "chosen_word", "response",
                 "train_of_thought"],
    "additionalProperties": False,
}


# Same schema with the train of thought removed. Built by copy rather than written out
# twice so the two can't drift - a duplicated description is a description that will be
# edited in one place only.
_MOVE_SCHEMA_NO_TOT = {
    **MOVE_SCHEMA,
    "properties": {k: v for k, v in MOVE_SCHEMA["properties"].items()
                   if k != "train_of_thought"},
    "required": [k for k in MOVE_SCHEMA["required"] if k != "train_of_thought"],
}
