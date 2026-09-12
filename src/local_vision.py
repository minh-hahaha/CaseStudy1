"""Local image captioning with BLIP, on the Space's own compute.

Shared by both generation paths: the remote and local products differ only in
the text step, which keeps the report's performance comparison to a single
variable. The assignment permits this — "the locally executed approach may use
either an LLM or another appropriate machine learning model".

Uses ``BlipProcessor`` + ``BlipForConditionalGeneration`` directly rather than
``pipeline("image-to-text")``. That task name was removed in Transformers v5,
so the pipeline route would break the Space on any unpinned install; the
processor/model API is stable across v4 and v5.
"""

from . import compute

MODEL_ID = "Salesforce/blip-image-captioning-base"
DEFAULT_MAX_NEW_TOKENS = 40
FALLBACK_DESCRIPTION = "an image"

_MODEL = None
_PROCESSOR = None


def _get_model():  # pragma: no cover - needs a model download and a GPU
    """Load the processor and model once per process and cache them."""
    global _MODEL, _PROCESSOR
    if _MODEL is None:
        from transformers import BlipForConditionalGeneration, BlipProcessor

        _PROCESSOR = BlipProcessor.from_pretrained(MODEL_ID)
        _MODEL = BlipForConditionalGeneration.from_pretrained(MODEL_ID).to(
            compute.get_device()
        )
    return _PROCESSOR, _MODEL


@compute.gpu(duration=60)
def describe_image(image, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> str:
    """Return a one-line description of a PIL image."""
    if image is None:
        raise ValueError("No image supplied.")

    processor, model = _get_model()
    inputs = processor(images=image, return_tensors="pt").to(model.device)
    tokens = model.generate(**inputs, max_new_tokens=max_new_tokens)
    text = processor.decode(tokens[0], skip_special_tokens=True).strip()
    return text or FALLBACK_DESCRIPTION
