"""Hardware detection so identical code runs on ZeroGPU, on CPU, and in CI.

The class example (``example.py``) hardcodes ``device="cuda"`` and imports
``spaces`` at module level, which is fine for code that only ever runs on a
Hugging Face Space. Deliverable 2b requires the test suite to run in GitHub
Actions, where neither ``spaces`` nor ``torch`` is installed, and development
happens on a Mac with no CUDA. This module is the single place that difference
is resolved; everything else can pretend it is always on the Space.
"""

import os
from collections.abc import Callable

DEFAULT_GPU_DURATION = 60


def _spaces_module():
    """Return the ``spaces`` module when running on HF Spaces, else ``None``."""
    try:
        import spaces
    except ImportError:
        return None
    return spaces


def is_zero_gpu() -> bool:
    """True when the ZeroGPU runtime is available."""
    return _spaces_module() is not None


def is_on_space() -> bool:
    """True when running inside a Hugging Face Space.

    ``SPACE_ID`` is the canonical marker. Used to gate OAuth: Gradio's
    ``LoginButton`` raises at construction time off-Spaces unless a token is
    already present, which would stop local development dead.
    """
    return bool(os.environ.get("SPACE_ID"))


def gpu(duration: int = DEFAULT_GPU_DURATION) -> Callable:
    """Request a ZeroGPU slice on Spaces; pass through everywhere else.

    Applied at decoration time, so it must not touch torch.
    """
    spaces = _spaces_module()
    if spaces is None:
        return lambda fn: fn
    return spaces.GPU(duration=duration)


def get_device() -> str:
    """Return ``"cuda"`` on ZeroGPU/CUDA hosts, ``"cpu"`` otherwise.

    Imports torch lazily, so this may only be called from inside a model
    loader — never at module import time.
    """
    if is_zero_gpu():
        return "cuda"

    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"
