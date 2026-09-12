# Citations

All external models, documentation, and LLM assistance used to build MemeForge.

## Starting point

- **DS/CS553 class example** (`example.py` in this repository) — the chatbot Space template
  demonstrating both an API-based model and a locally hosted Transformers pipeline.
  MemeForge follows its structure directly: the `Qwen/Qwen3-0.6B` and `openai/gpt-oss-20b`
  model choices, the `gr.LoginButton` / `gr.OAuthToken` authentication flow, the
  `InferenceClient` call shape, the `dtype="auto"` pipeline construction, the `[MODE]`
  logging convention, and the `fancy_css` stylesheet (container width, centered title and
  subtitle, bordered rounded panel, and the `max-width: 768px` media query), adapted to
  MemeForge's element ids.

## Models

- **`Salesforce/blip-image-captioning-base`** — local image captioning (vision step).
  BLIP, Li et al., *"BLIP: Bootstrapping Language-Image Pre-training for Unified
  Vision-Language Understanding and Generation"* (2022).
  https://huggingface.co/Salesforce/blip-image-captioning-base
- **`openai/gpt-oss-20b`** — remotely hosted caption writer, reached through the Hugging
  Face Inference API. https://huggingface.co/openai/gpt-oss-20b
- **`Qwen/Qwen3-0.6B`** — locally executed caption writer and failover target.
  https://huggingface.co/Qwen/Qwen3-0.6B

## Documentation

- Gradio documentation — https://www.gradio.app/docs
- Gradio on Spaces / OAuth (`hf_oauth`) — https://huggingface.co/docs/hub/spaces-oauth
- Spaces configuration reference — https://huggingface.co/docs/hub/spaces-config-reference
- Managing Spaces with GitHub Actions — https://huggingface.co/docs/hub/spaces-github-actions
- ZeroGPU / `spaces` decorator — https://huggingface.co/docs/hub/spaces-zerogpu
- `huggingface_hub.InferenceClient` — https://huggingface.co/docs/huggingface_hub/guides/inference
- Transformers pipelines — https://huggingface.co/docs/transformers/main_classes/pipelines
- Qwen3 chat template and `enable_thinking` — https://huggingface.co/Qwen/Qwen3-0.6B#switching-between-thinking-and-non-thinking-mode
- Pillow `ImageDraw.text` stroke and anchor options — https://pillow.readthedocs.io
- GitHub Actions documentation — https://docs.github.com/actions
- Discord "Intro to Webhooks" — https://support.discord.com/hc/en-us/articles/228383668
- Hugging Face pricing (for the report's cost analysis) — https://huggingface.co/pricing

## LLM assistance

- **Claude (Anthropic), Opus 5, via Claude Code** — wrote the build handoff specification,
  extracted and interpreted the assignment PDF, designed the architecture (shared local BLIP
  with the remote/local seam at the text-generation step), and implemented `app.py`, all
  modules under `src/`, the `tests/` suite, `.github/workflows/test.yml`, this file, and
  `README.md`. It also made the following design corrections during the build, which are
  reflected in the code: replacing an initially planned `google/flan-t5-base` local model
  with `Qwen/Qwen3-0.6B`, adding the `src/compute.py` hardware shim, pinning
  `gradio[oauth]==6.26.0` to match `sdk_version`, and gating `gr.LoginButton` on `SPACE_ID`.

_Note for the report: items 4g and 4h are marked "LLM only" and 4i and 4j "Human only".
Record the model, the complete prompt, and the full response for 4g and 4h, and write 4i and
4j without LLM assistance._
