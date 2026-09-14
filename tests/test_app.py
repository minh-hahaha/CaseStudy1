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
from src.styles import STYLES

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
    # The Meme Factory click declares five outputs (including the scene cache).
    result = app.run_factory(_image(), "Dad Joke", "", 2, router.AUTO_MODE)

    assert len(result) == 5


def test_run_factory_reports_the_serving_model_and_the_scene():
    scene_md, status_md, _picker, _meme, scene_state = app.run_factory(
        _image(), "Dad Joke", "", 2, router.AUTO_MODE
    )

    assert SCENE in scene_md
    assert router.REMOTE_LABEL in status_md
    assert "Vision (local BLIP)" in status_md
    assert scene_state == SCENE


def test_run_factory_surfaces_failover_in_the_status_block(monkeypatch):
    def remote_down(*args, **kwargs):
        raise remote_llm.RemoteCaptionError("503 provider down")

    monkeypatch.setattr(remote_llm, "generate_captions", remote_down)

    _scene, status_md, _picker, _meme, _state = app.run_factory(
        _image(), "Dad Joke", "", 2, router.AUTO_MODE
    )

    assert router.LOCAL_LABEL in status_md
    assert "503 provider down" in status_md


def test_run_factory_without_an_image_asks_for_one():
    _scene, status_md, _picker, _meme, scene_state = app.run_factory(
        None, "Dad Joke", "", 2, router.AUTO_MODE
    )

    assert status_md == app.UPLOAD_PROMPT
    assert scene_state == ""


def test_burn_caption_returns_a_rendered_image():
    source = _image()

    update = app.burn_caption(source, "a caption", "Bottom")
    rendered = update["value"]

    assert rendered.size == source.size
    assert rendered.tobytes() != source.tobytes()


def test_burn_caption_labels_the_output_with_the_caption_text():
    update = app.burn_caption(_image(), "a caption", "Bottom")

    assert "a caption" in update["label"]


def test_burn_caption_without_a_caption_returns_nothing():
    assert app.burn_caption(_image(), "", "Bottom") is None
    assert app.burn_caption(None, "a caption", "Bottom") is None


def test_random_settings_returns_a_valid_style_and_topic():
    style, topic = app.random_settings()

    assert style in STYLES
    assert topic in app.SURPRISE_TOPICS


def test_reroll_captions_without_a_prior_scene_asks_to_generate_first():
    status, picker = app.reroll_captions("", "Dad Joke", "", 2, router.AUTO_MODE)

    assert status == app.NO_SCENE_YET
    assert picker["choices"] == []


def test_reroll_captions_never_touches_blip(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("Reroll must not rerun BLIP.")

    monkeypatch.setattr(local_vision, "describe_image", forbidden)

    status, picker = app.reroll_captions(SCENE, "Dad Joke", "", 2, router.AUTO_MODE)

    assert "cached, not rerun" in status
    assert picker["choices"] == ["remote one", "remote two"]


def test_add_to_history_appends_the_new_meme():
    history, gallery_update = app.add_to_history(_image(), "a caption", [])

    assert len(history) == 1
    assert history[0][1] == "a caption"
    assert gallery_update["value"] == history


def test_add_to_history_ignores_a_missing_meme():
    history, _gallery_update = app.add_to_history(None, "a caption", [("prior", "x")])

    assert history == [("prior", "x")]


def test_add_to_history_caps_at_the_limit():
    history = [(f"meme-{i}", str(i)) for i in range(app.HISTORY_LIMIT)]

    updated, _gallery_update = app.add_to_history(_image(), "newest", history)

    assert len(updated) == app.HISTORY_LIMIT
    assert updated[-1][1] == "newest"
    assert updated[0] != history[0]


def test_run_style_gallery_returns_one_item_per_style():
    header, items = app.run_style_gallery(_image(), "", router.AUTO_MODE)

    assert SCENE in header
    assert len(items) == len(STYLES)


def test_run_style_gallery_without_an_image_asks_for_one():
    header, items = app.run_style_gallery(None, "", router.AUTO_MODE)

    assert header == app.UPLOAD_PROMPT
    assert items == []


def test_run_style_gallery_reports_a_per_style_failure_without_crashing(monkeypatch):
    def boom(*a, **k):
        raise remote_llm.RemoteCaptionError("503 down")

    monkeypatch.setattr(remote_llm, "generate_captions", boom)
    monkeypatch.setattr(local_llm, "generate_captions", boom)

    _header, items = app.run_style_gallery(_image(), "", router.REMOTE_ONLY_MODE)

    assert any("failed" in label for _img, label in items)


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
