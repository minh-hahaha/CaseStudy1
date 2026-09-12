"""Render a caption onto an image in the classic top/bottom meme layout."""

import textwrap

MIN_FONT_SIZE = 18
WIDTH_DIVISOR = 12
CHAR_WIDTH_RATIO = 0.55
MIN_WRAP_CHARS = 12
MARGIN_RATIO = 0.04
LINE_HEIGHT_RATIO = 1.15
STROKE_DIVISOR = 12
MIN_STROKE_WIDTH = 2


def _load_font(size: int):
    """Load a scalable font.

    Uses the face bundled with Pillow rather than shipping a .ttf: Hugging Face
    rejects pushes containing binary files stored as ordinary blobs, which made
    the Space sync fail. Pillow 10+ returns a real scalable TrueType here, not
    the old fixed-size bitmap font.
    """
    from PIL import ImageFont

    return ImageFont.load_default(size)


def render_meme(image, top_text: str = "", bottom_text: str = ""):
    """Return a *new* PIL image with stroked white caption text burned in.

    Never mutates the input image.
    """
    from PIL import ImageDraw

    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    width, height = canvas.size

    size = max(MIN_FONT_SIZE, width // WIDTH_DIVISOR)
    font = _load_font(size)
    wrap_at = max(MIN_WRAP_CHARS, int(width / (size * CHAR_WIDTH_RATIO)))
    margin = int(height * MARGIN_RATIO)
    line_height = size * LINE_HEIGHT_RATIO
    stroke_width = max(MIN_STROKE_WIDTH, size // STROKE_DIVISOR)

    for text, anchor_y, is_top in (
        (top_text, margin, True),
        (bottom_text, height - margin, False),
    ):
        if not text.strip():
            continue

        lines = textwrap.wrap(text.upper(), width=wrap_at)
        for index, line in enumerate(lines):
            y = (
                anchor_y + index * line_height
                if is_top
                else anchor_y - (len(lines) - index) * line_height
            )
            draw.text(
                (width / 2, y),
                line,
                font=font,
                fill="white",
                stroke_width=stroke_width,
                stroke_fill="black",
                anchor="ma",
            )

    return canvas
