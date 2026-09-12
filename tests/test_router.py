"""Failover tests for Deliverable 6. Every model call is monkeypatched."""

import pytest

from src import local_llm, remote_llm, router


@pytest.fixture(autouse=True)
def stub_local(monkeypatch):
    """Stand in for the local model so no download or GPU is needed."""
    monkeypatch.setattr(
        local_llm, "generate_captions", lambda *a, **k: ["local caption"]
    )


def _raise_remote(message):
    def boom(*a, **k):
        raise remote_llm.RemoteCaptionError(message)

    return boom


def test_remote_success_is_labelled_remote(monkeypatch):
    # Arrange
    monkeypatch.setattr(
        remote_llm, "generate_captions", lambda *a, **k: ["remote caption"]
    )

    # Act
    result = router.make_captions("a cat", "Dad Joke")

    # Assert
    assert result["captions"] == ["remote caption"]
    assert result["source"] == router.REMOTE_LABEL
    assert result["note"] == ""


def test_remote_failure_falls_over_to_local(monkeypatch):
    monkeypatch.setattr(
        remote_llm, "generate_captions", _raise_remote("429 rate limited")
    )

    result = router.make_captions("a cat", "Dad Joke")

    assert result["captions"] == ["local caption"]
    assert result["source"] == router.LOCAL_LABEL
    assert "429" in result["note"]


def test_simulated_outage_triggers_failover():
    result = router.make_captions("a cat", "Dad Joke", simulate_outage=True)

    assert result["source"] == router.LOCAL_LABEL
    assert "Simulated outage" in result["note"]


def test_remote_only_mode_does_not_fail_over(monkeypatch):
    monkeypatch.setattr(remote_llm, "generate_captions", _raise_remote("503 down"))

    result = router.make_captions(
        "a cat", "Dad Joke", mode=router.REMOTE_ONLY_MODE
    )

    assert result["captions"] == []
    assert result["source"] == router.REMOTE_LABEL
    assert "failover is disabled" in result["note"]


def test_local_only_mode_never_calls_the_remote_api(monkeypatch):
    # Arrange: make any remote call an outright test failure.
    def forbidden(*a, **k):
        raise AssertionError("Local-only mode must not touch the network.")

    monkeypatch.setattr(remote_llm, "generate_captions", forbidden)

    # Act
    result = router.make_captions("a cat", "Dad Joke", mode=router.LOCAL_ONLY_MODE)

    # Assert
    assert result["captions"] == ["local caption"]
    assert result["source"] == router.LOCAL_LABEL
    assert "No API call was made" in result["note"]


def test_double_failure_reports_both_paths(monkeypatch):
    monkeypatch.setattr(remote_llm, "generate_captions", _raise_remote("timeout"))

    def local_boom(*a, **k):
        raise local_llm.LocalCaptionError("no usable caption")

    monkeypatch.setattr(local_llm, "generate_captions", local_boom)

    result = router.make_captions("a cat", "Dad Joke")

    assert result["captions"] == []
    assert "timeout" in result["note"]
    assert "Local path also failed" in result["note"]


def test_result_always_reports_elapsed_time(monkeypatch):
    monkeypatch.setattr(
        remote_llm, "generate_captions", lambda *a, **k: ["remote caption"]
    )

    result = router.make_captions("a cat", "Dad Joke")

    assert result["elapsed"] >= 0


def test_auto_is_the_default_mode():
    assert router.MODES[0] == router.AUTO_MODE
