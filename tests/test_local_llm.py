"""Local path tests. The transformers pipeline is faked; no model is downloaded."""

import pytest

from src import local_llm
from src.local_llm import LocalCaptionError


class _FakeTokenizer:
    def __init__(self, recorder):
        self._recorder = recorder

    def apply_chat_template(self, messages, **kwargs):
        self._recorder["messages"] = messages
        self._recorder.update(kwargs)
        return "RENDERED PROMPT"


class _FakePipe:
    def __init__(self, output, recorder):
        self.tokenizer = _FakeTokenizer(recorder)
        self._output = output
        self._recorder = recorder

    def __call__(self, prompt, **kwargs):
        self._recorder["prompt"] = prompt
        self._recorder.update(kwargs)
        return [{"generated_text": self._output}]


@pytest.fixture
def fake_pipe(monkeypatch):
    """Install a fake pipeline and return the recorder it writes into."""
    recorder = {}

    def install(output):
        monkeypatch.setattr(
            local_llm, "_get_pipe", lambda: _FakePipe(output, recorder)
        )
        return recorder

    return install


def test_generate_captions_returns_parsed_captions(fake_pipe):
    # Arrange
    fake_pipe('{"captions": ["local one", "local two"]}')

    # Act
    captions = local_llm.generate_captions("a cat", "Dad Joke", n=2)

    # Assert
    assert captions == ["local one", "local two"]


def test_reasoning_mode_is_disabled_for_qwen(fake_pipe):
    recorder = fake_pipe('{"captions": ["x"]}')

    local_llm.generate_captions("a cat", "Dad Joke")

    assert recorder["enable_thinking"] is False
    assert recorder["add_generation_prompt"] is True


def test_local_path_uses_the_same_shared_messages_as_remote(fake_pipe):
    recorder = fake_pipe('{"captions": ["x"]}')

    local_llm.generate_captions("a cat on a laptop", "Dad Joke", n=3)

    roles = [m["role"] for m in recorder["messages"]]
    assert roles == ["system", "user"]
    assert "a cat on a laptop" in recorder["messages"][1]["content"]


def test_temperature_is_floored_to_keep_sampling_varied(fake_pipe):
    recorder = fake_pipe('{"captions": ["x"]}')

    local_llm.generate_captions("a cat", "Dad Joke", temperature=0.2)

    assert recorder["temperature"] == local_llm.MIN_TEMPERATURE


def test_think_blocks_are_stripped_from_the_output(fake_pipe):
    fake_pipe('<think>hmm</think>{"captions": ["clean caption"]}')

    assert local_llm.generate_captions("a cat", "Dad Joke") == ["clean caption"]


def test_unusable_output_raises_local_caption_error(fake_pipe):
    fake_pipe("?\n?")

    with pytest.raises(LocalCaptionError, match="no usable caption"):
        local_llm.generate_captions("a cat", "Dad Joke")
