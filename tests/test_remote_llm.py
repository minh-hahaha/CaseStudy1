"""Remote path tests. The InferenceClient is faked; no network call is made."""

import huggingface_hub
import pytest

from src import remote_llm
from src.remote_llm import RemoteCaptionError, resolve_token


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _fake_client(content=None, error=None, recorder=None):
    """Build an InferenceClient stand-in that returns content or raises."""

    class FakeClient:
        def __init__(self, **kwargs):
            if recorder is not None:
                recorder.update(kwargs)

        def chat_completion(self, **kwargs):
            if recorder is not None:
                recorder.update(kwargs)
            if error is not None:
                raise error
            return _FakeResponse(content)

    return FakeClient


@pytest.fixture
def token_env(monkeypatch):
    """Supply a token the way the Space secret does, via the environment."""
    monkeypatch.setenv("HF_TOKEN", "env-token")
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: "env-token")


def test_resolve_token_prefers_the_oauth_token(token_env):
    assert resolve_token("oauth-token") == "oauth-token"


def test_resolve_token_falls_back_to_the_space_secret(token_env):
    assert resolve_token(None) == "env-token"


def test_resolve_token_falls_back_to_a_local_cli_login(monkeypatch):
    # Arrange: no env var, but `hf auth login` wrote a token file.
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: "file-token")

    assert resolve_token(None) == "file-token"


def test_resolve_token_raises_when_no_token_exists(monkeypatch):
    # Patch get_token too, or a logged-in dev machine would pass this test
    # for the wrong reason.
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)

    with pytest.raises(RemoteCaptionError, match="No Hugging Face token"):
        resolve_token(None)


def test_generate_captions_returns_parsed_captions(monkeypatch, token_env):
    # Arrange
    monkeypatch.setattr(
        huggingface_hub,
        "InferenceClient",
        _fake_client(content='{"captions": ["remote one", "remote two"]}'),
    )

    # Act
    captions = remote_llm.generate_captions("a cat", "Dad Joke", n=2)

    # Assert
    assert captions == ["remote one", "remote two"]


def test_generate_captions_passes_the_model_to_the_client(monkeypatch, token_env):
    recorder = {}
    monkeypatch.setattr(
        huggingface_hub,
        "InferenceClient",
        _fake_client(content='{"captions": ["x"]}', recorder=recorder),
    )

    remote_llm.generate_captions("a cat", "Dad Joke", model="some/model")

    assert recorder["model"] == "some/model"
    assert recorder["token"] == "env-token"


def test_transport_errors_become_remote_caption_errors(monkeypatch, token_env):
    monkeypatch.setattr(
        huggingface_hub,
        "InferenceClient",
        _fake_client(error=TimeoutError("read timed out")),
    )

    with pytest.raises(RemoteCaptionError, match="TimeoutError"):
        remote_llm.generate_captions("a cat", "Dad Joke")


def test_empty_response_becomes_a_remote_caption_error(monkeypatch, token_env):
    monkeypatch.setattr(huggingface_hub, "InferenceClient", _fake_client(content=""))

    with pytest.raises(RemoteCaptionError, match="empty response"):
        remote_llm.generate_captions("a cat", "Dad Joke")


def test_unparseable_response_becomes_a_remote_caption_error(monkeypatch, token_env):
    monkeypatch.setattr(huggingface_hub, "InferenceClient", _fake_client(content="?\n?"))

    with pytest.raises(RemoteCaptionError):
        remote_llm.generate_captions("a cat", "Dad Joke")


def test_missing_token_raises_before_any_client_is_built(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)

    def forbidden(**kwargs):
        raise AssertionError("Must not build a client without a token.")

    monkeypatch.setattr(huggingface_hub, "InferenceClient", forbidden)

    with pytest.raises(RemoteCaptionError):
        remote_llm.generate_captions("a cat", "Dad Joke")
