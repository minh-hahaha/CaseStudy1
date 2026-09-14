# MemeForge — Case Study 1 Report

> Scaffold only. Sections marked **[DRAFT]** are pre-filled from the repository and should
> be reviewed/trimmed by the team. Sections marked **[TODO]**, **[LLM only]**, and
> **[Human only]** must be completed by the team before submission. Target length for the
> final submission is 1-2 pages — cut prose accordingly.

## a. Members' names

[TODO: list every team member's full name.]

## b. Description of the product, its purpose, and target audience [DRAFT]

MemeForge is a meme-caption generator built with Gradio and hosted on Hugging Face Spaces.
A user uploads an image, picks a caption "voice" (style), and optionally a topic hook;
the app describes the image, writes captions in that voice, and burns the chosen caption
onto the image in the classic top/bottom meme layout.

Target audience: instructors, TAs, and students who want a fast, on-topic, work-safe meme
for a slide or a chat message without manually captioning an image. The style presets
(Dad Joke, Corporate LinkedIn, Gen-Z Chaos, Professor Energy, etc. — see `src/styles.py`)
are aimed specifically at a classroom/office context rather than general meme-making.

[TODO: adjust framing/target audience if the team wants a different angle.]

## c. Description of the models used [DRAFT]

| Model | Role | Architecture (per model card) | Training data (per model card) |
|---|---|---|---|
| `Salesforce/blip-image-captioning-base` | Scene description (vision), always local | BLIP: ViT image encoder + BERT-based text decoder, trained with a bootstrapped caption-filtering scheme | Web image-text pairs, filtered/re-captioned by BLIP's own captioner-filter to reduce noise |
| `openai/gpt-oss-20b` | Remote caption writer (Deliverable 1) | Open-weight transformer, mixture-of-experts, reasoning-oriented (emits a separate reasoning channel before its answer — see `src/remote_llm.py`'s handling of `finish_reason`/reasoning field) | Not fully disclosed by OpenAI; general-purpose pretraining + instruction/RL post-training per the model card |
| `Qwen/Qwen3-0.6B` | Local caption writer (Deliverable 2) and failover target (Deliverable 6) | Dense transformer, small enough to run without a dedicated GPU; supports a switchable "thinking" mode (disabled here via `enable_thinking=False`, see `src/local_llm.py`) | Multilingual pretraining corpus per the Qwen3 technical report |

[TODO: verify these architecture/training claims against the current model cards linked in
CITATIONS.md before submitting — model cards are updated over time and this table was
drafted from general knowledge, not re-verified against the live pages.]

Both text models are fed the *identical* system + user prompt (`src/styles.py`'s
`build_messages`), so the only variable between the two paths is the model itself — this is
what makes the performance comparison in section d meaningful.

## d. Performance analysis [TODO — needs real measurements]

Use `scripts/compare_models.py` (see README) to collect timings across several runs, or the
Model Lab tab for a quick one-off comparison. Fill in after running:

| Metric | Remote (`gpt-oss-20b`) | Local (`Qwen3-0.6B`) |
|---|---|---|
| Mean latency (BLIP + caption gen), N=[ ] runs | [ ]s | [ ]s |
| Failure rate observed | [ ]/[ ] | [ ]/[ ] |
| Caption quality (subjective, 1-5) | [ ] | [ ] |
| Resource usage | Network + remote compute only | ZeroGPU allocation on this Space |

[TODO: note any qualitative differences you observed — tone, formatting reliability,
adherence to the requested style, how often the local model needed a retry, etc.]

## e. Cost-based analysis [TODO — needs current pricing]

Check current rates at https://huggingface.co/pricing before filling this in; do not reuse
numbers from an LLM's training data, since Hugging Face's pricing changes over time.

Suggested structure:

- **Remote path cost**: `(tokens per request) × (requests per user) × (1,000 users) ×
  (current $/token or $/request for gpt-oss-20b via Inference Providers)`. Note that
  Inference Providers may bill per-request or route to a third-party provider with its own
  rate — check which applies to `openai/gpt-oss-20b` specifically.
- **Local path cost**: dominated by the Space's compute tier (ZeroGPU quota is shared and
  rate-limited per user/Space; a free-tier Space may throttle under 1,000-user load, so
  consider whether a paid Spaces hardware tier is needed at that scale) rather than a
  per-request charge.
- **Rate limits**: note any request-per-minute or concurrent-request caps on the free
  Inference Providers tier and on ZeroGPU, and how those interact with the failover logic
  in `src/router.py` (a rate limit is one of the failure types it already detects).

[TODO: fill in the actual numbers and a one-paragraph conclusion — is 1,000 users
realistic on the current tier, or would you need to upgrade?]

## f. Comments and/or concerns [DRAFT]

- **Prompt injection via the topic field.** `topic` is free text that gets concatenated
  directly into the user prompt (`src/styles.py: build_user_prompt`). The system prompt
  carries a safety guardrail (no slurs, no identifier-style captions), but a user could
  attempt to override it through the topic field. Low severity here since the only output
  is caption text rendered onto an image, but worth flagging.
- **Dependence on an external API.** The remote path depends on Hugging Face Inference
  Providers' uptime, latency, and pricing for a model MemeForge doesn't control. The
  failover system (Deliverable 6) mitigates unavailability but not a raised price or a
  deprecated model.
- **Scalability of the local path.** ZeroGPU allocations are shared and time-boxed
  (`@spaces.GPU(duration=...)` in `src/local_llm.py` / `src/local_vision.py`); under
  concurrent load from many users, local (and failover) requests may queue or be throttled
  in a way a single-user demo won't reveal.
- **Data privacy.** Uploaded images are sent to BLIP locally and, on the remote path, the
  resulting *scene description* (not the raw image) is sent to the Inference API. No image
  bytes leave the Space on the remote path — only derived text. Worth stating explicitly in
  the report since it's a meaningful privacy property.
- **No caching or deduplication.** Identical requests re-run the full pipeline every time
  (see README's Known Limitations); at scale this is wasted compute and cost.

[TODO: add or remove points to match what the team actually wants to discuss; 2 points on
the rubric means this should stay short.]

## g. [LLM only] Established LLM's suggested improvement

**Model used:** Claude Sonnet 5 (Anthropic), via Claude Code, 2026-09-14.

**Complete prompt given:**

> Analyze this Gradio meme-caption app's prompt-construction and routing code (BLIP scene
> description → shared system/user prompt → remote LLM via Hugging Face InferenceClient, or
> a local Qwen3-0.6B model, with automatic failover between them). The user supplies an
> optional free-text "topic" field that is concatenated directly into the LLM user prompt
> alongside a fixed system prompt that forbids slurs and other unsafe content. Identify one
> meaningful improvement related to performance, reliability, scalability, cost, security,
> or maintainability.

**Complete response:**

> The most concrete improvement is hardening the prompt boundary around the free-text
> `topic` field. Right now the system prompt's safety guardrail is the only thing standing
> between a user's topic text and the model's output, and because both remote and local
> models receive the same messages, a jailbreak attempt only has to work once to affect
> both paths. Two changes would meaningfully reduce this risk without adding much
> complexity: (1) cap the topic field's length and strip obvious instruction-override
> patterns (e.g. "ignore previous instructions") before it reaches `build_user_prompt`,
> and (2) restate the safety constraint *after* the user content in the prompt, not just
> in the system message — models are measurably more likely to honor an instruction that
> appears closer to the end of the context window. This is a maintainability-friendly fix
> because it lives entirely in `src/styles.py`'s prompt construction, requires no new
> dependencies, and is easy to unit test (the project already has thorough prompt-related
> tests in `tests/test_styles.py` to extend).

## h. [LLM only] Weaker/local LLM's answer to the same question

**Model used:** `Qwen/Qwen3-0.6B` (the project's own local model).

**Same prompt as section g**, asked directly of Qwen3-0.6B (not through the app's
caption-writing prompt template — ask it the question above verbatim, e.g. via a quick
`transformers` `pipeline("text-generation", model="Qwen/Qwen3-0.6B")` call, or adapt
`scripts/compare_models.py`).

**Response:** [TODO — run the prompt above against Qwen3-0.6B and paste its complete,
unedited response here. Do not paraphrase or clean it up; a rougher answer here is expected
and is part of the comparison in section i.]

## i. [Human only] Comparison of the two responses

[TODO — this section must be written by the team without LLM assistance. Compare
usefulness, accuracy, and actionability of the two responses from sections g and h.
Call out anything incorrect, vague, or questionable in either response, and state which
suggestions you would actually implement and why.]

## j. [Human only] Deployment recommendation

[TODO — this section must be written by the team without LLM assistance. State which model
you would choose for a real deployment and why. Discuss whether the answer changes if cost,
privacy, or reliability were the top priority instead.]

---

See [CITATIONS.md](CITATIONS.md) for the full citation list (models, documentation, LLM
assistance) required alongside this report. Any LLM assistance used while writing sections
b, c, d, e, or f beyond what's already in CITATIONS.md must be added there too.
