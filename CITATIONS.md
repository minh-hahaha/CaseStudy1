# Citations

All external models, documentation, and LLM assistance used to build Meme Creator.

## Models

- **`Salesforce/blip-image-captioning-base`** — local image captioning (vision step).
  BLIP, Li et al., *"BLIP: Bootstrapping Language-Image Pre-training for Unified
  Vision-Language Understanding and Generation"* (2022).
  https://huggingface.co/Salesforce/blip-image-captioning-base
- **`openai/gpt-oss-20b`** — remotely hosted caption writer, reached through the Hugging
  Face Inference API. https://huggingface.co/openai/gpt-oss-20b
- **`Qwen/Qwen3-0.6B`** — locally executed caption writer and failover target.
  https://huggingface.co/Qwen/Qwen3-0.6B

## LLM assistance

**Claude Opus 5 via Claude Code** was used as an assistant during development. We directed
the project and made its design decisions. Claude assisted with the following:

- Discussing architecture options, including the design of a shared local BLIP model with
  the remote/local split at the text-generation step.
- Implementing `app.py`, the modules under `src/`, the `tests/` suite,
  `.github/workflows/test.yml`, this file, and `README.md`.
