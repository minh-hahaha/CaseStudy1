"""Meme rendering tests. Uses PIL only, no model."""

from PIL import Image

from src.meme_render import render_meme

SIZE = (400, 400)


def _blank():
    return Image.new("RGB", SIZE, "white")


def test_render_preserves_image_size():
    rendered = render_meme(_blank(), bottom_text="hello world")

    assert rendered.size == SIZE


def test_render_actually_draws_pixels():
    source = _blank()

    rendered = render_meme(source, bottom_text="hello world")

    assert rendered.tobytes() != source.tobytes()


def test_render_does_not_mutate_the_input_image():
    # Arrange
    source = _blank()
    before = source.tobytes()

    # Act
    render_meme(source, top_text="top", bottom_text="bottom")

    # Assert
    assert source.tobytes() == before


def test_blank_caption_leaves_the_image_untouched():
    source = _blank()

    rendered = render_meme(source, top_text="   ", bottom_text="")

    assert rendered.tobytes() == source.tobytes()


def test_renders_both_top_and_bottom():
    top_only = render_meme(_blank(), top_text="alpha")
    both = render_meme(_blank(), top_text="alpha", bottom_text="omega")

    assert top_only.tobytes() != both.tobytes()


def test_font_honours_the_requested_size():
    # Guards the pillow>=10.1 floor: older versions ignore the size argument
    # and silently render unreadably small text.
    from src.meme_render import _load_font

    assert _load_font(64).getbbox("WWW") != _load_font(12).getbbox("WWW")


def test_handles_non_rgb_image_modes():
    # Gradio's uploaded image can arrive in any PIL mode depending on the
    # source file (grayscale scan, transparent PNG, palette GIF); render_meme
    # must not assume RGB going in.
    for mode in ("L", "RGBA", "P"):
        source = Image.new(mode, SIZE)

        rendered = render_meme(source, bottom_text="hello world")

        assert rendered.mode == "RGB"
        assert rendered.size == SIZE


def test_handles_a_caption_with_no_spaces_to_wrap_on():
    # textwrap.wrap must not crash or drop the caption when it can't find a
    # word boundary to break on.
    long_word = "a" * 200

    rendered = render_meme(_blank(), bottom_text=long_word)

    assert rendered.size == SIZE
    assert rendered.tobytes() != _blank().tobytes()


def test_long_uppercase_caption_stays_inside_the_side_margins():
    # Wide capitals overflowed when wrapping guessed character widths.
    width, height = 766, 766
    source = Image.new("RGB", (width, height), "white")

    rendered = render_meme(source, top_text="when the reasoning model finally answers")

    edge = max(2, width // 100)
    for x in (*range(edge), *range(width - edge, width)):
        column = rendered.crop((x, 0, x + 1, height))
        assert column.tobytes() == source.crop((x, 0, x + 1, height)).tobytes()
