"""Prometheus metrics for Meme Creator (Case Study 3, Deliverable 2b).

Every metric the product exports is defined here, so the list lives in one
place. app.py starts the HTTP server that serves them on port 8000.
"""

import functools

from prometheus_client import Counter, Gauge, Histogram, start_http_server

METRICS_PORT = 8000

# 1. Traffic and errors: one count per button click, by outcome.
REQUESTS = Counter(
    "meme_requests_total",
    "UI requests handled, by action and outcome.",
    ["action", "status"],
)

# 2. Load right now: requests currently being processed.
INFLIGHT = Gauge(
    "meme_inflight_requests",
    "Requests currently being processed.",
)

# 3. How long local BLIP takes to describe an image.
VISION_SECONDS = Histogram(
    "meme_vision_seconds",
    "Time spent describing an image with local BLIP.",
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16),
)

# 4. How long caption generation takes, by path (remote/local) and outcome.
CAPTION_SECONDS = Histogram(
    "meme_caption_seconds",
    "Time spent generating captions, by serving path and outcome.",
    ["path", "outcome"],
    buckets=(0.5, 1, 2, 4, 8, 16, 32, 64, 128),
)

# 5. Which model actually produced the captions.
CAPTION_SOURCE = Counter(
    "meme_caption_source_total",
    "Caption requests by the path that produced the final answer.",
    ["path"],
)

# 6. Remote API failed and the local model took over.
FAILOVERS = Counter(
    "meme_failovers_total",
    "Times the remote API failed and the local model served instead.",
)

# 7. Output volume.
CAPTIONS_RETURNED = Counter(
    "meme_captions_returned_total",
    "Individual captions returned to users.",
)

# 8. Size of uploaded images, which drives BLIP time and memory.
IMAGE_MEGAPIXELS = Histogram(
    "meme_image_megapixels",
    "Size of uploaded images in megapixels.",
    buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16),
)


def start_metrics_server(port: int = METRICS_PORT) -> None:
    """Serve /metrics over HTTP on its own port, next to Gradio."""
    start_http_server(port)


def track(action: str, failed=None):
    """Decorator: count a handler's calls and outcome, and track in-flight.

    status is "error" if the handler raises, "failed" if it returns but
    failed(result) says the user got nothing useful, otherwise "ok".
    functools.wraps keeps the original name and signature, which Gradio
    needs to inject the OAuth token and name the API endpoint.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            INFLIGHT.inc()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                REQUESTS.labels(action=action, status="error").inc()
                raise
            finally:
                INFLIGHT.dec()
            status = "failed" if failed is not None and failed(result) else "ok"
            REQUESTS.labels(action=action, status=status).inc()
            return result

        return wrapper

    return decorator


def observe_caption(path: str, outcome: str, seconds: float, count: int) -> None:
    """Record one caption attempt on path ("remote" or "local")."""
    CAPTION_SECONDS.labels(path=path, outcome=outcome).observe(seconds)
    if outcome == "ok":
        CAPTION_SOURCE.labels(path=path).inc()
        CAPTIONS_RETURNED.inc(count)


def observe_image(image) -> None:
    """Record the size of an uploaded PIL image."""
    width, height = image.size
    IMAGE_MEGAPIXELS.observe(width * height / 1_000_000)