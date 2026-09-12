"""Remote path tests. The InferenceClient is faked; no network call is made."""

import huggingface_hub
import pytest

from src import remote_llm
from src.remote_llm import RemoteCaptionError, candidate_tokens


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


def _client_factory(behaviour, recorder):
    """Build an InferenceClient stand-in driven by a per-token behaviour map."""

    class FakeClient:
        def __init__(self, **kwargs):
            self._token = kwargs.get("token")
            recorder.setdefault("constructed", []).append(kwargs)

        def chat_completion(self, **kwargs):
            recorder.setdefault("calls", []).append(self._token)
            recorder.update(kwargs)
            outcome = behaviour(self._token)
            if isinstance(outcome, Exception):
                raise outcome
            return _FakeResponse(outcome)

    return FakeClient


@pytest.fixture
def fake_client(monkeypatch):
    """Install a fake client; `behaviour(token)` returns content or an Exception."""

    def install(behaviour):
        recorder = {}
        monkeypatch.setattr(
            huggingface_hub, "InferenceClient", _client_factory(behaviour, recorder)
        )
        return recorder

    return install


@pytest.fixture
def space_token(monkeypatch):
    """Supply a Space secret the way Hugging Face injects it."""
    monkeypatch.setenv("HF_TOKEN", "space-token")
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: "space-token")


@pytest.fixture
def no_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(huggingface_hub, "get_token", lambda: None)


# --- token resolution ------------------------------------------------------


def test_oauth_token_is_tried_before_the_space_token(space_token):
    assert candidate_tokens("oauth-token") == ["oauth-token", "space-token"]


def test_space_token_is_used_when_nobody_is_logged_in(space_token):
    assert candidate_tokens(None) == ["space-token"]


def test_duplicate_tokens_are_not_tried_twice(space_token):
    assert candidate_tokens("space-token") == ["space-token"]


def test_no_candidates_when_no_token_exists(no_token):
    assert candidate_tokens(None) == []


# --- generation ------------------------------------------------------------


def test_returns_parsed_captions(space_token, fake_client):
    fake_client(lambda token: '{"captions": ["remote one", "remote two"]}')

    assert remote_llm.generate_captions("a cat", "Dad Joke", n=2) == [
        "remote one",
        "remote two",
    ]


def test_passes_the_model_to_the_client(space_token, fake_client):
    recorder = fake_client(lambda token: '{"captions": ["x"]}')

    remote_llm.generate_captions("a cat", "Dad Joke", model="some/model")

    assert recorder["constructed"][0]["model"] == "some/model"
    assert recorder["constructed"][0]["token"] == "space-token"


def test_oauth_403_falls_back_to_the_space_token(space_token, fake_client):
    """The real failure seen on the Space: an OAuth grant without inference scope."""
    # Arrange
    forbidden = Exception(
        "403 Forbidden: This authentication method does not have sufficient "
        "permissions to call Inference Providers"
    )

    def behaviour(token):
        return forbidden if token == "oauth-token" else '{"captions": ["rescued"]}'

    recorder = fake_client(behaviour)

    # Act
    captions = remote_llm.generate_captions(
        "a cat", "Dad Joke", token="oauth-token"
    )

    # Assert: it retried with the Space token instead of giving up.
    assert captions == ["rescued"]
    assert recorder["calls"] == ["oauth-token", "space-token"]


def test_every_token_failing_raises_with_all_reasons(space_token, fake_client):
    fake_client(lambda token: Exception(f"403 denied for {token}"))

    with pytest.raises(RemoteCaptionError) as excinfo:
        remote_llm.generate_captions("a cat", "Dad Joke", token="oauth-token")

    message = str(excinfo.value)
    assert "oauth-token" in message and "space-token" in message


def test_long_provider_errors_are_truncated_for_the_ui(space_token, fake_client):
    fake_client(lambda token: Exception("x" * 5000))

    with pytest.raises(RemoteCaptionError) as excinfo:
        remote_llm.generate_captions("a cat", "Dad Joke")

    assert len(str(excinfo.value)) < 600


def test_timeout_becomes_a_remote_caption_error(space_token, fake_client):
    fake_client(lambda token: TimeoutError("read timed out"))

    with pytest.raises(RemoteCaptionError, match="TimeoutError"):
        remote_llm.generate_captions("a cat", "Dad Joke")


def test_empty_response_becomes_a_remote_caption_error(space_token, fake_client):
    fake_client(lambda token: "")

    with pytest.raises(RemoteCaptionError, match="empty response"):
        remote_llm.generate_captions("a cat", "Dad Joke")


def test_unparseable_response_becomes_a_remote_caption_error(space_token, fake_client):
    fake_client(lambda token: "?\n?")

    with pytest.raises(RemoteCaptionError):
        remote_llm.generate_captions("a cat", "Dad Joke")


def test_missing_token_raises_before_any_client_is_built(no_token, monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("Must not build a client without a token.")

    monkeypatch.setattr(huggingface_hub, "InferenceClient", forbidden)

    with pytest.raises(RemoteCaptionError, match="No Hugging Face token"):
        remote_llm.generate_captions("a cat", "Dad Joke")
