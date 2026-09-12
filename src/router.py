"""Routing and failover between the remote and local caption models.

This module *is* Deliverable 6. All failover logic lives here and nowhere else,
so the behaviour has exactly one place to be read, tested, and demonstrated.
"""

import time

from . import local_llm, remote_llm

AUTO_MODE = "Auto (remote, fail over to local)"
REMOTE_ONLY_MODE = "Remote only"
LOCAL_ONLY_MODE = "Local only (no API calls)"
MODES = [AUTO_MODE, REMOTE_ONLY_MODE, LOCAL_ONLY_MODE]

REMOTE_LABEL = f"Remote API path: BLIP + {remote_llm.DEFAULT_MODEL}"
LOCAL_LABEL = f"Local path: BLIP + {local_llm.MODEL_ID}"


def _result(captions, source, start, note=""):
    """Shape every return value identically so the UI has one contract."""
    return {
        "captions": captions,
        "source": source,
        "elapsed": time.perf_counter() - start,
        "note": note,
    }


def _serve_locally(scene, style, n, temperature, topic, start, note):
    """Run the local path, reporting a readable note if it also fails."""
    print("[MODE] local")
    try:
        captions = local_llm.generate_captions(scene, style, n, temperature, topic)
    except local_llm.LocalCaptionError as exc:
        reasons = [note, f"Local path also failed: {exc}"]
        return _result([], LOCAL_LABEL, start, " — ".join(r for r in reasons if r))
    return _result(captions, LOCAL_LABEL, start, note)


def make_captions(
    scene: str,
    style: str,
    n: int = 3,
    temperature: float = 0.9,
    topic: str = "",
    mode: str = AUTO_MODE,
    simulate_outage: bool = False,
    token: str | None = None,
) -> dict:
    """Produce captions and report which model actually served the request.

    Returns a dict with keys ``captions``, ``source``, ``elapsed`` and ``note``.
    The ``source`` value satisfies Deliverable 6c: the caller can always state
    which model handled the request.
    """
    start = time.perf_counter()

    if mode == LOCAL_ONLY_MODE:
        return _serve_locally(
            scene, style, n, temperature, topic, start,
            "Local-only mode selected. No API call was made.",
        )

    try:
        if simulate_outage:
            raise remote_llm.RemoteCaptionError("Simulated outage (demo toggle).")
        print("[MODE] api")
        captions = remote_llm.generate_captions(
            scene, style, n, temperature, topic=topic, token=token
        )
        return _result(captions, REMOTE_LABEL, start)
    except remote_llm.RemoteCaptionError as exc:
        if mode == REMOTE_ONLY_MODE:
            return _result(
                [], REMOTE_LABEL, start,
                f"Remote call failed and failover is disabled. {exc}",
            )
        return _serve_locally(
            scene, style, n, temperature, topic, start,
            f"Remote path failed, served locally instead. Reason: {exc}",
        )
