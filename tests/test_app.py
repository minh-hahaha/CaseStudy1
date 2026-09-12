"""UI glue tests for app.py.

Skipped in CI, where gradio is deliberately absent from requirements-ci.txt.
Run locally to catch output-arity mismatches between a handler and its
``outputs=`` list, which Gradio reports only at request time.
"""

import pytest

pytest.importorskip("gradio", reason="gradio is not a CI dependency")

from PIL import Image

import app
from src import local_llm, local_vision, remote_llm, router

SCENE = "two cats sleeping on a couch"


@pytest.fixture(autouse=True)
def stub_models(monkeypatch):
    """Replace every model call with a fast stand-in."""
    monkeypatch.setattr(local_vision, "describe_image", lambda image, **k: SCENE)
    monkeypatch.setattr(
        remote_llm, "generate_captions", lambda *a, **k: ["remote one", "remote two"]
    )
    monkeypatch.setattr(local_llm, "generate_captions", lambda *a, **k: ["local one"])


def _image():
    return Image.new("RGB", (320, 240), "white")


def test_run_factory_returns_one_value_per_declared_output():
    # The Meme Factory click declares four outputs.
    result = app.run_factory(_image(), "Dad Joke", "", 2, 0.9, router.AUTO_MODE, False)

    assert len(result) == 4


def test_run_factory_reports_the_serving_model_and_the_scene():
    scene_md, status_md, _picker, _meme = app.run_factory(
        _image(), "Dad Joke", "", 2, 0.9, router.AUTO_MODE, False
    )

    assert SCENE in scene_md
    assert router.REMOTE_LABEL in status_md
    assert "Vision (local BLIP)" in status_md


def test_run_factory_surfaces_failover_in_the_status_block():
    _scene, status_md, _picker, _meme = app.run_factory(
        _image(), "Dad Joke", "", 2, 0.9, router.AUTO_MODE, True
    )

    assert router.LOCAL_LABEL in status_md
    assert "Simulated outage" in status_md


def test_run_factory_without_an_image_asks_for_one():
    _scene, status_md, _picker, _meme = app.run_factory(
        None, "Dad Joke", "", 2, 0.9, router.AUTO_MODE, False
    )

    assert status_md == app.UPLOAD_PROMPT


def test_burn_caption_returns_a_rendered_image():
    source = _image()

    rendered = app.burn_caption(source, "a caption", "Bottom")

    assert rendered.size == source.size
    assert rendered.tobytes() != source.tobytes()


def test_burn_caption_without_a_caption_returns_nothing():
    assert app.burn_caption(_image(), "", "Bottom") is None
    assert app.burn_caption(None, "a caption", "Bottom") is None


def test_run_bakeoff_returns_one_value_per_declared_output():
    # The Model Lab click declares three outputs.
    result = app.run_bakeoff(_image(), "Dad Joke", "")

    assert len(result) == 3


def test_run_bakeoff_shows_both_models_and_all_three_timings():
    header, remote_out, local_out = app.run_bakeoff(_image(), "Dad Joke", "")

    assert "Local vision:" in header and "Remote text:" in header
    assert "Local text:" in header
    assert "remote one" in remote_out
    assert "local one" in local_out


def test_run_bakeoff_reports_a_remote_failure_without_crashing(monkeypatch):
    def boom(*a, **k):
        raise remote_llm.RemoteCaptionError("503 provider down")

    monkeypatch.setattr(remote_llm, "generate_captions", boom)

    _header, remote_out, local_out = app.run_bakeoff(_image(), "Dad Joke", "")

    assert "503 provider down" in remote_out
    assert "local one" in local_out
