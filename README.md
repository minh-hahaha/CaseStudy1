---
title: MemeForge
emoji: 🔥
colorFrom: purple
colorTo: pink
sdk: gradio
sdk_version: 6.26.0
python_version: '3.12'
app_file: app.py
hf_oauth: true
pinned: false
short_description: Turn any image into class-ready meme captions, remote or local.
---

# 🔥 MemeForge

Meme caption generator for **DS/CS553 Case Study 1**. Upload an image, pick a voice, get
class-ready captions, render the meme.

Professors, teachers, and anyone who opens a meeting with a meme need one fast, on-topic,
and safe for a work audience. MemeForge takes a screenshot or photo and returns captions in
a chosen voice, then burns the caption into the image.

## Architecture

One product, two interchangeable generation paths. Both take the same image and return the
same thing; only the text-generation step differs, which makes the remote-vs-local
comparison in the report a single-variable experiment.

```
                                    ┌─ remote: openai/gpt-oss-20b  ──┐
image ──> BLIP (local, always) ──>  │  (InferenceClient)             │ ──> captions ──> PIL render
          scene description         └─ local:  Qwen/Qwen3-0.6B ──────┘
                                       (on this Space's ZeroGPU)
```

| Component | Model | Where it runs | Serves |
|---|---|---|---|
| Vision | `Salesforce/blip-image-captioning-base` | Local (ZeroGPU) | Both paths |
| Text, remote | `openai/gpt-oss-20b` | Remote, `huggingface_hub.InferenceClient` | Deliverable 1 |
| Text, local | `Qwen/Qwen3-0.6B` | Local (ZeroGPU) | Deliverables 2 and 6 |

The assignment permits this split: *"the locally executed approach may use either an LLM or
another appropriate machine learning model."* In **Local only** mode no network call is made
at all.

## Routing and failover (extra credit)

The **Routing** control under *Generation settings* selects:

- **Auto (remote, fail over to local)** — default. Tries the remote LLM, and on any failure
  automatically serves the request from the local model instead.
- **Remote only** — no failover, so a remote failure is visible rather than papered over.
- **Local only (no API calls)** — nothing leaves the host.

The status panel always names the model that actually served the request. Failures detected
automatically: missing token, provider/HTTP error, timeout, rate limit, empty response, and
unparseable response. The **Simulate remote API outage** checkbox forces the failure path for
demonstration; logging out of the sidebar triggers the same failover through a genuine error.

## Layout

```
app.py                   Gradio UI: Meme Factory tab + Model Lab tab
src/compute.py           ZeroGPU / CPU / CI hardware shim
src/styles.py            Caption styles and shared prompt construction
src/parsing.py           Shared response parsing for both paths
src/local_vision.py      BLIP image captioning (local)
src/remote_llm.py        Remote caption generation via the Inference API
src/local_llm.py         Local caption generation with Qwen3
src/router.py            Routing and failover (Deliverable 6)
src/meme_render.py       Caption-to-image rendering
tests/                   pytest suite, runs with no model downloads
```

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export HF_TOKEN=hf_...        # needed for the remote path
python app.py
```

The sidebar login button only appears on a Space; locally the app reads `HF_TOKEN` instead.

## Tests

```bash
pip install -r requirements-ci.txt
pytest -q --cov=src --cov-report=term-missing
```

Every model call is monkeypatched, so the suite needs neither a GPU nor a model download and
runs in under a second. `requirements-ci.txt` deliberately omits torch and transformers;
`src/` imports them lazily inside functions so this stays true.

## Links

- Hugging Face Space: https://huggingface.co/spaces/minh-hahaha/CaseStudy1
- GitHub repository: https://github.com/minh-hahaha/CaseStudy1

See [CITATIONS.md](CITATIONS.md) for models, documentation, and LLM assistance.
