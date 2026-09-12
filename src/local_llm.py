"""Local caption generation with Qwen3, on the Space's own compute.

Deliverable 2 (the locally executed product) and the failover target for
Deliverable 6. Uses the same model as the class example, and is fed the *same*
chat messages as the remote path via ``styles.build_messages`` — that shared
prompt is what makes the remote-vs-local comparison in the report honest.
"""

from . import compute
from .parsing import CaptionParseError, parse_caption_payload
from .styles import build_messages

MODEL_ID = "Qwen/Qwen3-0.6B"
MAX_NEW_TOKENS = 256
MIN_TEMPERATURE = 0.7
TOP_P = 0.95

_PIPE = None


def _get_pipe():  # pragma: no cover - needs a model download and a GPU
    """Build the text-generation pipeline once per process and cache it."""
    global _PIPE
    if _PIPE is None:
        from transformers import pipeline

        _PIPE = pipeline(
            "text-generation",
            model=MODEL_ID,
            dtype="auto",
            device=compute.get_device(),
        )
    return _PIPE


class LocalCaptionError(RuntimeError):
    """Raised for any failure of the local caption path."""


def _build_prompt(pipe, scene: str, style: str, n: int, topic: str) -> str:
    """Render the shared chat messages with Qwen3's reasoning mode disabled.

    Without ``enable_thinking=False`` Qwen3 emits ``<think>`` blocks that
    consume the whole token budget before producing a caption.
    """
    return pipe.tokenizer.apply_chat_template(
        build_messages(scene, style, n, topic),
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


@compute.gpu(duration=90)
def generate_captions(
    scene: str,
    style: str,
    n: int = 3,
    temperature: float = 0.9,
    topic: str = "",
) -> list[str]:
    """Return up to ``n`` captions from the locally executed LLM.

    Makes no network calls, which is how Deliverable 2a is demonstrated.
    Raises ``LocalCaptionError`` when the model produces nothing usable.
    """
    pipe = _get_pipe()
    prompt = _build_prompt(pipe, scene, style, n, topic)

    outputs = pipe(
        prompt,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=True,
        temperature=max(temperature, MIN_TEMPERATURE),
        top_p=TOP_P,
        return_full_text=False,
    )
    raw = (outputs[0].get("generated_text") or "").strip()

    try:
        return parse_caption_payload(raw, n)
    except CaptionParseError as exc:
        raise LocalCaptionError(f"{MODEL_ID} produced no usable caption: {exc}") from exc
