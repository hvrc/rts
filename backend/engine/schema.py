"""The structured output every provider must return.

This is the contract between the engine and whatever brain is plugged in. A provider's
only job is to return a dict matching MOVE_SCHEMA — how it gets there (Anthropic
structured outputs, an OpenAI-compatible json_schema, a local model coaxed with a
json_object hint) is the provider's problem, not the engine's.
"""

MOVE_SCHEMA = {
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
