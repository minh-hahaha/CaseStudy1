"""Render a caption onto an image in the classic top/bottom meme layout."""

MIN_FONT_SIZE = 14
WIDTH_DIVISOR = 18
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


def _wrap_to_width(text: str, font, max_width: float, stroke_width: int) -> list[str]:
    """Greedily wrap ``text`` so each line's rendered width fits ``max_width``.

    Measures with the real font instead of guessing a per-character width,
    which let wide capitals run off the image edges. A single word wider than
    the limit still gets its own line rather than being dropped.
    """
    lines: list[str] = []
    for word in text.split():
        candidate = f"{lines[-1]} {word}" if lines else word
        fits = font.getlength(candidate) + 2 * stroke_width <= max_width
        lines = [*lines[:-1], candidate] if lines and fits else [*lines, word]
    return lines


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
    margin = int(height * MARGIN_RATIO)
    max_line_width = width - 2 * int(width * MARGIN_RATIO)
    line_height = size * LINE_HEIGHT_RATIO
    stroke_width = max(MIN_STROKE_WIDTH, size // STROKE_DIVISOR)

    for text, anchor_y, is_top in (
        (top_text, margin, True),
        (bottom_text, height - margin, False),
    ):
        if not text.strip():
            continue

        lines = _wrap_to_width(text.upper(), font, max_line_width, stroke_width)
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
