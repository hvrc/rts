"""The frozen frontend contract.

  POST /echo  -> {response, train_of_thought: [[...]], response_code}
  POST /reset -> {response, train_of_thought}

`response_code == "UNRELATED"` is the only code the UI treats specially (it stamps a
"?" on the player's bubble). Everything else just displays `response`. Keep this the
single place that shapes the payload so the UI can't be broken from three directions.
"""


def contract(response_code, response, train_of_thought=None, link=None, new_game=False):
    """`link` is the relationship the AI just played: {"from": <word it connected from>,
    "to": <word it chose>}. Present only on OK. The UI needs it so a thumbs-up/down on a
    bot bubble can record *which link* the human liked - rating a bare word would be
    meaningless.

    `new_game` marks the turn that ended a game and started a fresh one - a loss, or an
    explicit restart. The chain and the used-words set are empty again from here, so
    every word is free to be replayed. The chat history in the UI is untouched; only the
    game behind it is new.
    """
    payload = {
        "response": response,
        "train_of_thought": train_of_thought or [],
        "response_code": response_code,
    }
    if link:
        payload["link"] = link
    if new_game:
        payload["new_game"] = True
    return payload


def error(exc):
    return {
        "response": "?",
        "train_of_thought": [],
        "response_code": "ERROR",
        "error": str(exc),
    }


def clean_train_of_thought(tot, chosen, rule):
    """Guarantee the train of thought is a legal narrowing sequence ending in the
    chosen word, with no candidates that break the letter rule. Repair rather than
    trust blindly - the animation reads this array literally."""
    try:
        lists = [[str(w) for w in lst if isinstance(w, str)] for lst in tot]
    except TypeError:
        lists = []
    lists = [[w for w in lst if rule.allows(w)] for lst in lists]
    lists = [lst for lst in lists if lst]
    if not lists:
        lists = [[chosen]]
    if lists[-1] != [chosen]:
        lists.append([chosen])
    return lists
