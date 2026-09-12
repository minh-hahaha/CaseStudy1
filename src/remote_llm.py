"""Remote caption generation through the Hugging Face Inference API.

Deliverable 1: the remotely hosted LLM. The whole purpose of this module is to
fail in a *catchable* way — every failure path raises ``RemoteCaptionError`` so
``router`` has exactly one exception type to handle.
"""

from .parsing import CaptionParseError, parse_caption_payload
from .styles import build_messages

DEFAULT_MODEL = "openai/gpt-oss-20b"
REQUEST_TIMEOUT_SECONDS = 25
MAX_RESPONSE_TOKENS = 400
MAX_REASON_CHARS = 220


class RemoteCaptionError(RuntimeError):
    """Raised for any failure of the remote caption path."""


def candidate_tokens(token: str | None = None) -> list[str]:
    """Return the tokens to try, in order: viewer's OAuth token, then the Space's.

    A list rather than a single token is deliberate. A Gradio OAuth token only
    carries inference permission when the Space declares the ``inference-api``
    scope, and a viewer's own inference credits can run out. Falling back to the
    Space's own ``HF_TOKEN`` keeps the remote path alive instead of silently
    demoting every logged-in visitor to the local model.
    """
    from huggingface_hub import get_token

    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in (token, get_token()):
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _request_captions(
    api_key: str,
    scene: str,
    style: str,
    n: int,
    temperature: float,
    topic: str,
    model: str,
) -> str:
    """Make one chat completion call and return the raw reply text."""
    from huggingface_hub import InferenceClient

    client = InferenceClient(
        model=model, token=api_key, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response = client.chat_completion(
        messages=build_messages(scene, style, n, topic),
        max_tokens=MAX_RESPONSE_TOKENS,
        temperature=temperature,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise RemoteCaptionError("Remote model returned an empty response.")
    return raw


def _short(reason: str) -> str:
    """Keep a provider error readable in the UI status panel."""
    collapsed = " ".join(reason.split())
    if len(collapsed) <= MAX_REASON_CHARS:
        return collapsed
    return collapsed[:MAX_REASON_CHARS] + "…"


def generate_captions(
    scene: str,
    style: str,
    n: int = 3,
    temperature: float = 0.9,
    topic: str = "",
    model: str = DEFAULT_MODEL,
    token: str | None = None,
) -> list[str]:
    """Return up to ``n`` captions from the remotely hosted LLM.

    Tries each available token in turn, so a viewer whose OAuth grant lacks the
    inference scope still gets served via the Space's token. Raises
    ``RemoteCaptionError`` when every candidate fails.
    """
    candidates = candidate_tokens(token)
    if not candidates:
        raise RemoteCaptionError(
            "No Hugging Face token available. Log in with the button in the "
            "sidebar, set the HF_TOKEN secret on the Space, or run "
            "`hf auth login` locally."
        )

    failures: list[str] = []
    for api_key in candidates:
        try:
            raw = _request_captions(
                api_key, scene, style, n, temperature, topic, model
            )
        except RemoteCaptionError as exc:
            failures.append(_short(str(exc)))
            continue
        except Exception as exc:
            failures.append(_short(f"{type(exc).__name__}: {exc}"))
            continue

        try:
            return parse_caption_payload(raw, n)
        except CaptionParseError as exc:
            failures.append(_short(str(exc)))

    raise RemoteCaptionError(" | ".join(failures))
