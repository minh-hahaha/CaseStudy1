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


class RemoteCaptionError(RuntimeError):
    """Raised for any failure of the remote caption path."""


def resolve_token(token: str | None = None) -> str:
    """Resolve the API token: Gradio OAuth login first, then the Hub's own chain.

    Matches the class example's OAuth flow, then delegates to
    ``huggingface_hub.get_token()``, which reads the ``HF_TOKEN`` environment
    variable (how the Space secret arrives) and falls back to the token file
    written by ``hf auth login`` (how local development arrives). Reading only
    the environment variable would silently ignore a logged-in developer.
    """
    from huggingface_hub import get_token

    api_key = token or get_token()
    if not api_key:
        raise RemoteCaptionError(
            "No Hugging Face token available. Log in with the button in the "
            "sidebar, set the HF_TOKEN secret on the Space, or run "
            "`hf auth login` locally."
        )
    return api_key


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

    Raises ``RemoteCaptionError`` on a missing token, transport or provider
    error, timeout, rate limit, empty reply, or unparseable reply.
    """
    from huggingface_hub import InferenceClient

    api_key = resolve_token(token)

    try:
        client = InferenceClient(
            model=model, token=api_key, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response = client.chat_completion(
            messages=build_messages(scene, style, n, topic),
            max_tokens=MAX_RESPONSE_TOKENS,
            temperature=temperature,
        )
        raw = response.choices[0].message.content
    except RemoteCaptionError:
        raise
    except Exception as exc:
        raise RemoteCaptionError(f"{type(exc).__name__}: {exc}") from exc

    if not raw:
        raise RemoteCaptionError("Remote model returned an empty response.")

    try:
        return parse_caption_payload(raw, n)
    except CaptionParseError as exc:
        raise RemoteCaptionError(str(exc)) from exc
