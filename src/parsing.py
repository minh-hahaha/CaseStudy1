"""Shared response parsing for both caption generation paths.

Lives in its own module rather than inside ``remote_llm`` because both paths
now talk to chat models and must interpret their replies identically. The
tolerance here is load-bearing, not defensive padding: gpt-oss models can leak
reasoning prose into ``message.content`` depending on the serving provider, and
Qwen3 emits ``<think>`` blocks unless they are explicitly disabled.
"""

import json
import re

_THINK_BLOCK = re.compile(r"<think>.*?</think>", flags=re.DOTALL)
_THINK_TAIL = re.compile(r"<think>.*$", flags=re.DOTALL)
_CODE_FENCE = re.compile(r"^```(?:json)?|```$", flags=re.MULTILINE)
_JSON_START = re.compile(r"[\{\[]")
# gpt-oss "harmony" output: when a provider flattens the channels into content,
# the answer follows the final-channel marker and everything before it is reasoning.
_HARMONY_FINAL = re.compile(r"<\|channel\|>final<\|message\|>|assistantfinal")
_JSON_DECODER = json.JSONDecoder()
_LIST_NOISE = re.compile(r'^\s*(?:[-*•]|\d+[.)])\s*|^["\']|["\',]+$')

MIN_CAPTION_CHARS = 4


class CaptionParseError(RuntimeError):
    """Raised when no caption can be recovered from a model response."""


def strip_think_blocks(raw: str) -> str:
    """Remove Qwen-style ``<think>`` reasoning, including an unterminated tail."""
    without_blocks = _THINK_BLOCK.sub("", raw)
    return _THINK_TAIL.sub("", without_blocks).strip()


def strip_harmony_reasoning(raw: str) -> str:
    """Keep only the text after the last gpt-oss final-channel marker, if present."""
    return _HARMONY_FINAL.split(raw)[-1]


def _captions_from(parsed: object, n: int) -> list[str] | None:
    """Return cleaned captions from a decoded JSON value, or None if it has none."""
    captions = parsed.get("captions") if isinstance(parsed, dict) else parsed
    if not isinstance(captions, list):
        return None

    cleaned = [str(c).strip() for c in captions if str(c).strip()]
    return cleaned[:n] or None


def _from_json(text: str, n: int) -> list[str] | None:
    """Return captions from the first decodable JSON value in ``text`` that has them.

    Scans every opening bracket instead of one greedy span, so brackets inside
    leading prose (common in leaked reasoning) cannot hide the real payload.
    """
    for match in _JSON_START.finditer(text):
        try:
            parsed, _ = _JSON_DECODER.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        captions = _captions_from(parsed, n)
        if captions:
            return captions
    return None


def _from_lines(text: str, n: int) -> list[str]:
    """Fall back to line splitting so a formatting slip does not lose the request."""
    lines = (_LIST_NOISE.sub("", line).strip() for line in text.splitlines())
    return [line for line in lines if len(line) >= MIN_CAPTION_CHARS][:n]


def parse_caption_payload(raw: str, n: int, allow_lines: bool = True) -> list[str]:
    """Extract up to ``n`` captions from a model response.

    Tolerates reasoning blocks, code fences, leading prose, a bare JSON array,
    and plain numbered or bulleted lists. ``allow_lines=False`` disables the
    list fallback for models whose non-JSON output is reasoning prose rather
    than a formatting slip. Raises ``CaptionParseError`` when nothing usable
    remains.
    """
    visible = strip_harmony_reasoning(strip_think_blocks(raw or ""))
    text = _CODE_FENCE.sub("", visible).strip()

    from_json = _from_json(text, n)
    if from_json:
        return from_json

    from_lines = _from_lines(text, n) if allow_lines else []
    if from_lines:
        return from_lines

    raise CaptionParseError("Could not parse any caption from the model response.")
