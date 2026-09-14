"""Batch remote-vs-local caption comparison, for the report's item 4d/4e.

The Model Lab tab in app.py runs both paths once, interactively, on whatever
image is on screen. This script automates the same comparison across
multiple runs and styles on one image, so the report can cite an average
over several samples instead of a single anecdotal run.

Requires the full requirements.txt (torch, transformers, huggingface_hub)
since it exercises the real local model. Not part of the pytest suite or CI.

Usage:
    python scripts/compare_models.py path/to/image.jpg \
        --styles "Dad Joke" "Sarcastic" --runs 3 --out results.csv
"""

import argparse
import csv
import functools
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

from src import local_llm, local_vision, remote_llm
from src.styles import DEFAULT_STYLE, STYLES

FIELDNAMES = ["image", "style", "run", "path", "elapsed_seconds", "captions", "error"]


def _time_call(fn):
    """Run fn, returning (captions_or_None, error_or_None, elapsed_seconds)."""
    start = time.perf_counter()
    try:
        result = fn()
    except Exception as exc:
        return None, str(exc), time.perf_counter() - start
    return result, None, time.perf_counter() - start


def compare(
    image_path: Path, styles: list[str], n: int, runs: int, topic: str
) -> list[dict]:
    """Run both caption paths ``runs`` times per style and return one row per call."""
    image = Image.open(image_path).convert("RGB")
    scene = local_vision.describe_image(image)
    print(f"BLIP scene: {scene}")

    rows = []
    for style in styles:
        for run in range(1, runs + 1):
            calls = (
                (
                    "remote",
                    functools.partial(
                        remote_llm.generate_captions, scene, style, n, topic=topic
                    ),
                ),
                (
                    "local",
                    functools.partial(
                        local_llm.generate_captions, scene, style, n, topic=topic
                    ),
                ),
            )
            for path_name, fn in calls:
                captions, error, elapsed = _time_call(fn)
                rows.append(
                    {
                        "image": image_path.name,
                        "style": style,
                        "run": run,
                        "path": path_name,
                        "elapsed_seconds": round(elapsed, 3),
                        "captions": " | ".join(captions) if captions else "",
                        "error": error or "",
                    }
                )
                status = "ok" if error is None else f"FAILED: {error}"
                print(f"  [{path_name}] {style} run {run}: {elapsed:.2f}s ({status})")
    return rows


def summarize(rows: list[dict]) -> None:
    """Print mean latency per path across the successful runs."""
    by_path: dict[str, list[float]] = {}
    for row in rows:
        if not row["error"]:
            by_path.setdefault(row["path"], []).append(row["elapsed_seconds"])

    print("\nMean latency by path (successful runs only):")
    for path_name, timings in by_path.items():
        print(f"  {path_name}: {mean(timings):.2f}s over {len(timings)} run(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Path to a sample image")
    parser.add_argument(
        "--styles", nargs="+", default=[DEFAULT_STYLE], choices=list(STYLES)
    )
    parser.add_argument("--n", type=int, default=3, help="Captions requested per call")
    parser.add_argument("--runs", type=int, default=3, help="Repeats per style, per path")
    parser.add_argument("--topic", default="", help="Optional topic hook")
    parser.add_argument("--out", type=Path, default=Path("comparison_results.csv"))
    args = parser.parse_args()

    rows = compare(args.image, args.styles, args.n, args.runs, args.topic)

    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {args.out}")

    summarize(rows)


if __name__ == "__main__":
    main()
