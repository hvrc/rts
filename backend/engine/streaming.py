"""Reading a structured response while it is still being written.

Structured outputs arrive as JSON text, one token at a time. Waiting for the closing
brace before showing anything costs the whole generation - four to six seconds of a
blank screen for a reply that is usually one word.

This reads the fields out of the JSON as they land. It is a character scanner rather
than a repeated `json.loads` on the buffer, because a partial JSON document is not
valid JSON and never parses until the last byte; trying and catching would report
nothing until the moment it no longer matters.

Only top-level string fields are extracted, which is all the engine needs - the schema
puts `train_of_thought`, the one nested field, last. The authoritative parse still
happens at the end; this is for latency, not for correctness.
"""

_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b",
            "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


class FieldReader:
    """Feed it JSON text; it reports which string fields have appeared.

    `feed` returns a list of (field, delta, complete) tuples. `delta` is the new text
    for that field since the last call; `complete` marks its closing quote. Fields with
    no new characters aren't reported, so an empty list means "nothing yet".
    """

    def __init__(self):
        self._state = "seek"
        self._key = ""
        self._field = None
        self._escape = False
        self._hex = None      # non-None while collecting a \uXXXX escape
        self._depth = 0
        self._in_nested_string = False
        self.values = {}

    def feed(self, chunk):
        pending = {}
        finished = []

        def emit(text):
            pending[self._field] = pending.get(self._field, "") + text
            self.values[self._field] += text

        for ch in chunk:
            state = self._state

            if state == "seek":
                # Between tokens at the top level. Braces, commas and whitespace are
                # all noise; a quote starts a key.
                if ch == '"':
                    self._state, self._key = "key", ""

            elif state == "key":
                if self._escape:
                    self._key += _ESCAPES.get(ch, ch)
                    self._escape = False
                elif ch == "\\":
                    self._escape = True
                elif ch == '"':
                    self._state = "colon"
                else:
                    self._key += ch

            elif state == "colon":
                if ch == ":":
                    self._state = "value"

            elif state == "value":
                if ch == '"':
                    self._state, self._field = "string", self._key
                    self.values.setdefault(self._field, "")
                elif ch in "[{":
                    # Nested. Skipped wholesale: the engine reads nothing from inside a
                    # nested value, and descending would let a key *inside* the nesting
                    # be mistaken for a top-level one.
                    self._state = "nested"
                    self._depth = 1
                    self._in_nested_string = False
                elif ch not in " \t\r\n":
                    self._state = "scalar"

            elif state == "string":
                if self._hex is not None:
                    self._hex += ch
                    if len(self._hex) == 4:
                        try:
                            emit(chr(int(self._hex, 16)))
                        except ValueError:
                            pass          # malformed escape: drop it, keep the stream
                        self._hex = None
                elif self._escape:
                    self._escape = False
                    if ch == "u":
                        self._hex = ""
                    else:
                        emit(_ESCAPES.get(ch, ch))
                elif ch == "\\":
                    self._escape = True
                elif ch == '"':
                    finished.append(self._field)
                    self._state, self._field = "seek", None
                else:
                    emit(ch)

            elif state == "scalar":
                if ch in ",}":
                    self._state = "seek"

            elif state == "nested":
                # Strings inside the nesting can contain braces, so track them - a
                # bracket in a word would otherwise unbalance the depth count.
                if self._escape:
                    self._escape = False
                elif ch == "\\":
                    self._escape = True
                elif self._in_nested_string:
                    if ch == '"':
                        self._in_nested_string = False
                elif ch == '"':
                    self._in_nested_string = True
                elif ch in "[{":
                    self._depth += 1
                elif ch in "]}":
                    self._depth -= 1
                    if self._depth == 0:
                        self._state = "seek"

        out = [(f, d, False) for f, d in pending.items() if d]
        out += [(f, "", True) for f in finished]
        return out
