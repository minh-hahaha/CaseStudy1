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

Claude (Anthropic), via Claude Code, was used as an assistant throughout development. The
team directed the project and made its design decisions; Claude assisted with the following:

- **Opus 5** — wrote the build handoff specification, extracted and interpreted the
  assignment PDF, designed the architecture (shared local BLIP with the remote/local seam
  at the text-generation step), and implemented `app.py`, all modules under `src/`, the
  `tests/` suite, `.github/workflows/test.yml`, this file, and `README.md`. It also made the
  following design corrections during the build, which are reflected in the code: replacing
  an initially planned `google/flan-t5-base` local model with `Qwen/Qwen3-0.6B`, adding the
  `src/compute.py` hardware shim, pinning `gradio[oauth]==6.26.0` to match `sdk_version`, and
  gating `gr.LoginButton` on `SPACE_ID`.
- **Sonnet 5** — audited the repo against the full assignment rubric, then added:
  `pyproject.toml` (ruff lint config) and a lint step in `.github/workflows/test.yml`;
  edge-case tests in `tests/test_render.py` and `tests/test_router.py`;
  `scripts/compare_models.py` (batch remote-vs-local timing comparison); the "Model
  comparison for the report", "Known limitations", and failover trade-offs sections of
  `README.md`; a Discord-notification step in `.github/workflows/sync-to-hf.yml` (mirroring
  the existing one in `test.yml`); a report scaffold, including drafting a Deliverable 4g
  LLM-analysis prompt/response pair; and the Surprise Me / Reroll / session history / Style
  Gallery / accessible-alt-text features in `app.py`.
- **Opus 5** (continued, later session) — fixed the remote path leaking chain-of-thought
  reasoning into captions (`src/parsing.py`, `src/remote_llm.py`); fixed long uppercase
  captions overflowing the image margins (`src/meme_render.py`); renamed the product from
  MemeForge to Meme Creator throughout the UI, README, and this file; simplified the caption
  styles from six voices to four; and logged raw Model Lab timing runs in
  `PERFORMANCE_NOTES.md` for the report's performance-analysis section.
