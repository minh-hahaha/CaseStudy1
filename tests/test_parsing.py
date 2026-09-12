"""Parsing tests. No model is downloaded or called."""

import pytest

from src.parsing import CaptionParseError, parse_caption_payload, strip_think_blocks


def test_parses_clean_json_object():
    # Arrange
    raw = '{"captions": ["first one", "second one"]}'

    # Act
    captions = parse_caption_payload(raw, 3)

    # Assert
    assert captions == ["first one", "second one"]


def test_parses_fenced_json_block():
    raw = '```json\n{"captions": ["fenced caption"]}\n```'

    assert parse_caption_payload(raw, 3) == ["fenced caption"]


def test_parses_bare_json_array():
    raw = '["just an array", "of captions"]'

    assert parse_caption_payload(raw, 3) == ["just an array", "of captions"]


def test_parses_numbered_list_when_json_is_absent():
    raw = "1. first caption here\n2) second caption here\n- third caption here"

    assert parse_caption_payload(raw, 3) == [
        "first caption here",
        "second caption here",
        "third caption here",
    ]


def test_ignores_leading_prose_before_json():
    raw = 'Sure! Here are your captions:\n{"captions": ["actual caption"]}'

    assert parse_caption_payload(raw, 3) == ["actual caption"]


def test_truncates_to_requested_count():
    raw = '{"captions": ["one", "two", "three", "four"]}'

    assert parse_caption_payload(raw, 2) == ["one", "two"]


def test_raises_on_empty_response():
    with pytest.raises(CaptionParseError):
        parse_caption_payload("", 3)


def test_raises_when_nothing_usable_remains():
    with pytest.raises(CaptionParseError):
        parse_caption_payload("a\nb\nc", 3)


def test_strips_complete_think_block():
    raw = "<think>let me consider this</think>the answer"

    assert strip_think_blocks(raw) == "the answer"


def test_strips_unterminated_think_tail():
    raw = "visible text<think>cut off mid thought"

    assert strip_think_blocks(raw) == "visible text"


def test_parses_captions_hidden_behind_a_think_block():
    raw = '<think>planning the jokes</think>{"captions": ["survived reasoning"]}'

    assert parse_caption_payload(raw, 3) == ["survived reasoning"]


def test_malformed_json_falls_back_to_line_splitting():
    raw = '{"captions": ["unterminated'

    assert parse_caption_payload(raw, 3) == ['{"captions": ["unterminated']


def test_json_object_without_a_caption_list_falls_back_to_lines():
    raw = '{"result": "some caption text here"}'

    assert parse_caption_payload(raw, 3) == ['{"result": "some caption text here"}']


def test_non_list_caption_value_falls_back_to_lines():
    raw = '{"captions": "a single string not a list"}'

    assert parse_caption_payload(raw, 3) == ['{"captions": "a single string not a list"}']
