"""BLIP wrapper tests. The processor and model are faked; nothing is downloaded."""

import pytest

from src import local_vision


class _FakeTokens(list):
    pass


class _FakeProcessor:
    def __init__(self, generated_text, recorder):
        self._generated_text = generated_text
        self._recorder = recorder

    def __call__(self, images, return_tensors):
        self._recorder["images"] = images
        self._recorder["return_tensors"] = return_tensors
        return self

    def to(self, device):
        self._recorder["inputs_device"] = device
        return {}

    def decode(self, tokens, skip_special_tokens):
        self._recorder["skip_special_tokens"] = skip_special_tokens
        return self._generated_text


class _FakeModel:
    device = "cpu"

    def __init__(self, recorder):
        self._recorder = recorder

    def generate(self, **kwargs):
        self._recorder.update(kwargs)
        return [_FakeTokens([1, 2, 3])]


@pytest.fixture
def fake_blip(monkeypatch):
    """Install a fake processor/model pair and return the shared recorder."""

    def install(generated_text):
        recorder = {}
        processor = _FakeProcessor(generated_text, recorder)
        model = _FakeModel(recorder)
        monkeypatch.setattr(local_vision, "_get_model", lambda: (processor, model))
        return recorder

    return install


def test_describe_image_returns_the_stripped_description(fake_blip):
    fake_blip("  a cat asleep on a laptop  ")

    assert local_vision.describe_image(object()) == "a cat asleep on a laptop"


def test_describe_image_falls_back_when_blip_returns_nothing(fake_blip):
    fake_blip("")

    assert local_vision.describe_image(object()) == local_vision.FALLBACK_DESCRIPTION


def test_describe_image_passes_the_token_budget_through(fake_blip):
    recorder = fake_blip("a cat")

    local_vision.describe_image(object(), max_new_tokens=7)

    assert recorder["max_new_tokens"] == 7


def test_describe_image_decodes_without_special_tokens(fake_blip):
    recorder = fake_blip("a cat")

    local_vision.describe_image(object())

    assert recorder["skip_special_tokens"] is True
    assert recorder["return_tensors"] == "pt"


def test_describe_image_rejects_a_missing_image():
    with pytest.raises(ValueError, match="No image supplied"):
        local_vision.describe_image(None)
