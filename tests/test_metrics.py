"""Prometheus instrumentation tests (Case Study 3, Deliverable 2b).

Metrics live in the process-wide default registry, so each test compares a
before/after delta instead of absolute values.
"""

import pytest
from prometheus_client import REGISTRY

from src import local_llm, metrics, remote_llm, router


def _value(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture(autouse=True)
def stub_local(monkeypatch):
    monkeypatch.setattr(
        local_llm, "generate_captions", lambda *a, **k: ["local one", "local two"]
    )


def _remote_down(*args, **kwargs):
    raise remote_llm.RemoteCaptionError("503 provider down")


def test_remote_success_counts_as_remote_source(monkeypatch):
    monkeypatch.setattr(remote_llm, "generate_captions", lambda *a, **k: ["r1"])
    before_source = _value("meme_caption_source_total", path="remote")
    before_captions = _value("meme_captions_returned_total")
    before_obs = _value("meme_caption_seconds_count", path="remote", outcome="ok")

    router.make_captions("a cat", "Dad Joke")

    assert _value("meme_caption_source_total", path="remote") == before_source + 1
    assert _value("meme_captions_returned_total") == before_captions + 1
    assert (
        _value("meme_caption_seconds_count", path="remote", outcome="ok")
        == before_obs + 1
    )


def test_failover_is_counted_and_served_locally(monkeypatch):
    monkeypatch.setattr(remote_llm, "generate_captions", _remote_down)
    before_failovers = _value("meme_failovers_total")
    before_local = _value("meme_caption_source_total", path="local")
    before_remote_err = _value(
        "meme_caption_seconds_count", path="remote", outcome="error"
    )

    result = router.make_captions("a cat", "Dad Joke")

    assert result["source"] == router.LOCAL_LABEL
    assert _value("meme_failovers_total") == before_failovers + 1
    assert _value("meme_caption_source_total", path="local") == before_local + 1
    assert (
        _value("meme_caption_seconds_count", path="remote", outcome="error")
        == before_remote_err + 1
    )


def test_remote_only_failure_is_not_a_failover(monkeypatch):
    monkeypatch.setattr(remote_llm, "generate_captions", _remote_down)
    before = _value("meme_failovers_total")

    router.make_captions("a cat", "Dad Joke", mode=router.REMOTE_ONLY_MODE)

    assert _value("meme_failovers_total") == before


def test_local_failure_is_recorded_as_local_error(monkeypatch):
    def local_down(*a, **k):
        raise local_llm.LocalCaptionError("empty output")

    monkeypatch.setattr(local_llm, "generate_captions", local_down)
    before = _value("meme_caption_seconds_count", path="local", outcome="error")

    result = router.make_captions("a cat", "Dad Joke", mode=router.LOCAL_ONLY_MODE)

    assert result["captions"] == []
    assert (
        _value("meme_caption_seconds_count", path="local", outcome="error")
        == before + 1
    )


def test_track_labels_ok_failed_and_error_and_restores_inflight():
    @metrics.track("unit", failed=lambda result: result is None)
    def handler(value):
        if value == "boom":
            raise RuntimeError("boom")
        assert _value("meme_inflight_requests") >= 1
        return value

    inflight = _value("meme_inflight_requests")
    ok = _value("meme_requests_total", action="unit", status="ok")
    failed = _value("meme_requests_total", action="unit", status="failed")
    error = _value("meme_requests_total", action="unit", status="error")

    handler("fine")
    handler(None)
    with pytest.raises(RuntimeError):
        handler("boom")

    assert _value("meme_requests_total", action="unit", status="ok") == ok + 1
    assert _value("meme_requests_total", action="unit", status="failed") == failed + 1
    assert _value("meme_requests_total", action="unit", status="error") == error + 1
    assert _value("meme_inflight_requests") == inflight


def test_track_preserves_the_handler_name_and_signature():
    import inspect

    def original(image, hf_token: str | None = None):
        return image

    wrapped = metrics.track("unit")(original)

    assert wrapped.__name__ == "original"
    assert list(inspect.signature(wrapped).parameters) == ["image", "hf_token"]


def test_observe_image_records_megapixels():
    from PIL import Image

    before = _value("meme_image_megapixels_sum")

    metrics.observe_image(Image.new("RGB", (1000, 500)))

    assert _value("meme_image_megapixels_sum") == pytest.approx(before + 0.5)