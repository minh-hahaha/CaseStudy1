"""Style and prompt-construction tests. No model is downloaded or called."""

import pytest

from src.styles import (
    DEFAULT_STYLE,
    STYLES,
    SYSTEM_PROMPT,
    build_messages,
    build_user_prompt,
)


def test_every_style_has_a_non_empty_instruction():
    assert STYLES
    for name, instruction in STYLES.items():
        assert instruction.strip(), f"{name} has an empty instruction"


def test_default_style_is_a_real_style():
    assert DEFAULT_STYLE in STYLES


def test_user_prompt_includes_scene_and_requested_count():
    prompt = build_user_prompt("a cat asleep on a laptop", "Dad Joke", 4)

    assert "a cat asleep on a laptop" in prompt
    assert "Write 4 distinct captions" in prompt


def test_user_prompt_includes_style_instruction():
    prompt = build_user_prompt("a cat", "Dad Joke", 3)

    assert STYLES["Dad Joke"] in prompt


def test_user_prompt_includes_topic_when_given():
    prompt = build_user_prompt("a cat", "Dad Joke", 3, topic="gradient descent")

    assert "gradient descent" in prompt


def test_user_prompt_omits_topic_line_when_blank():
    prompt = build_user_prompt("a cat", "Dad Joke", 3, topic="   ")

    assert "Tie the captions" not in prompt


def test_unknown_style_raises_key_error():
    with pytest.raises(KeyError):
        build_user_prompt("a cat", "Nonexistent Style", 3)


def test_system_prompt_carries_the_safety_guardrail():
    assert "slurs" in SYSTEM_PROMPT


def test_build_messages_returns_system_then_user():
    messages = build_messages("a cat", "Dad Joke", 3)

    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert "a cat" in messages[1]["content"]


def test_system_prompt_forbids_identifier_style_captions():
    # Regression guard: Qwen3-0.6B returned ["cats_on_couch_groan", ...] without this.
    assert "underscore_name" in SYSTEM_PROMPT
