"""Caption style definitions and prompt construction.

Pure data and pure functions with no model dependencies, so the prompting
logic is fully unit-testable and is shared verbatim by both the remote and the
local generation path. Sharing it is what makes the remote-vs-local comparison
in the report a single-variable experiment.
"""

MAX_CAPTION_CHARS = 120

STYLES = {
    "Deadpan Academic": (
        "Write in a dry, understated academic register. Use precise vocabulary "
        "and treat something trivial with unwarranted scholarly seriousness. "
        "No exclamation marks."
    ),
    "Corporate LinkedIn": (
        "Write as an insufferable LinkedIn thought-leadership post. Start with a "
        "mundane observation, pivot to a grand business lesson. Short lines."
    ),
    "Gen-Z Chaos": (
        "Write in chaotic internet-native voice. Lowercase, fragmentary, "
        "absurdist. No hashtags. Do not overuse slang to the point of nonsense."
    ),
    "Dad Joke": (
        "Write a groan-inducing pun or wordplay caption. Family-friendly, "
        "deliberately corny, one clean setup and payoff."
    ),
    "Existential Dread": (
        "Write a caption that starts light and lands somewhere quietly bleak. "
        "Understated, not melodramatic."
    ),
    "Professor Energy": (
        "Write as a professor opening a lecture with a joke about their own "
        "course material. Self-aware, mildly smug, clearly enjoying themselves."
    ),
}

DEFAULT_STYLE = "Professor Energy"

SYSTEM_PROMPT = (
    "You are a meme caption writer. You produce short, punchy captions suitable "
    f"for a slide shown to a university class. Keep captions under {MAX_CAPTION_CHARS} "
    "characters. Each caption must be a natural English sentence or phrase that a "
    "person would actually say out loud — never a hashtag, slug, or "
    "underscore_name. Never produce slurs, sexual content, or insults aimed at "
    "real named people. Respond with JSON only, no prose, no code fences."
)
# The "natural English sentence" clause is a measured prompt iteration, not
# padding: without it Qwen3-0.6B returned identifier-style output
# (["cats_on_couch_groan", ...]) in 2 of 4 sampled runs, and 0 of 4 with it.


def build_user_prompt(scene: str, style: str, n: int, topic: str = "") -> str:
    """Build the user turn for the caption request.

    Raises ``KeyError`` if ``style`` is unknown, which is intentional: a bad
    style should fail loudly rather than silently produce generic output.
    """
    instruction = STYLES[style]
    topic_line = (
        f'Tie the captions to this topic if you can do it naturally: "{topic}".\n'
        if topic.strip()
        else ""
    )
    return (
        f'An image has been described as: "{scene}"\n'
        f"{topic_line}"
        f"Style guidance: {instruction}\n\n"
        f"Write {n} distinct captions. Return exactly this JSON shape:\n"
        '{"captions": ["first caption", "second caption"]}'
    )


def build_messages(scene: str, style: str, n: int, topic: str = "") -> list[dict]:
    """Build the chat message list used identically by both generation paths."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(scene, style, n, topic)},
    ]
