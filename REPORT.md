# Meme Creator: Case Study 1 Report

**Hugging Face Space:** https://huggingface.co/spaces/minh-hahaha/CaseStudy1
**GitHub:** https://github.com/minh-hahaha/CaseStudy1

## a. Members

- Minh Ha
- Max Jeronimo

*Note: We did this most of the project together in-person, pair programming, so most of the commits come under Minh (with Claude Code helps of course).*

## b. Product description

Meme Creator turns any image into a captioned meme. A user uploads a photo,
picks a voice (for example *Professor Energy*, *Dad Joke*, *Corporate LinkedIn*), and can add
an optional topic such as "midterm week". The app returns captions, and the chosen
one is rendered onto the image in the classic top/bottom meme style.

**Purpose:** make a fast, workplace-safe meme without writing the joke yourself.

**Target audience:** anyone really: professors, team managers, and presenters who open a lecture, presentation or meeting with a
meme, and students making slides.

## c. Models

| Model | Role | Runs |
|---|---|---|
| `Salesforce/blip-image-captioning-base` | Describes the image in one sentence | Locally, both paths |
| `openai/gpt-oss-20b` | Writes captions from that description | Remote, Inference API |
| `Qwen/Qwen3-0.6B` | Writes captions from that description | Locally on the Space |

**BLIP (base).** A vision-language model with a ViT-B/16 image encoder and a
transformer text decoder. It was pre-trained on about 129M image-text pairs (COCO, Visual
Genome, Conceptual Captions, SBU, and a LAION subset), with a caption bootstrapping step that
filters noisy web captions. This checkpoint was fine-tuned for captioning on COCO. Its job
here is to turn pixels into text so a text-only LLM can "joke" about the image.

**gpt-oss-20b.** OpenAI's open-weight reasoning model: a mixture-of-experts transformer with
about 21B total parameters, of which about 3.6B are active per token. It is served remotely
through `huggingface_hub.InferenceClient` with low reasoning effort.

**Qwen3-0.6B.** A dense decoder-only transformer with 0.6B parameters (28 layers,
grouped-query attention). It was pre-trained on about 36T tokens in 119 languages. Its
"thinking" mode is turned off so it answers directly within the token budget.

Both LLMs receive the **same prompt**, so the text model is the only thing that differs
between the two paths. No custom dataset was collected or used for training.

## d. Performance analysis

*[Fill in with numbers from the Model Lab tab. Run the same 3 to 5 images several times and
report the average.]*

| Metric | Remote (gpt-oss-20b) | Local (Qwen3-0.6B) |
|---|---|---|
| BLIP vision time (shared step) | 6.71s | 6.71s |
| Caption generation time | 0.64s | 8.03s |
| First request after idle (cold start) | 0.31s | 11.94s |
| Host resources | Network only | ZeroGPU slice, ~1.4 GB model |

Numbers are averages over 3 images x 4 runs each (1 cold start + 3 warm runs per image),
collected from the Model Lab tab on the deployed Space. BLIP vision time is a single shared
step (same call feeds both paths) — one outlier warm run (vision 19.51s, local text 16.96s,
likely a ZeroGPU slice reassignment) is excluded from the warm averages above.

*Observations:* the remote model (gpt-oss-20b) was both faster (well under 1s once warm,
vs. several seconds for the local model) and produced noticeably better meme captions,
funnier and more consistently on-style, than the local Qwen3-0.6B model.

## e. Cost analysis (1,000 users)

**LLM Assistance**: We used an LLM to help with these cost analysis. But pricing documents are cited. 

**Assumption:** 1,000 users x 5 requests/day = 5,000 requests/day, about 150,000
requests/month. Each caption request sends roughly 300 input tokens (BLIP description +
prompt) and returns roughly 400 output tokens (gpt-oss-20b's low-effort reasoning +
answer). Prices for
[Inference Providers pricing for gpt-oss-20b](https://huggingface.co/inference/models?search=gpt-oss-20b).

- **Shared BLIP cost:** the vision step (`Salesforce/blip-image-captioning-base`) runs on
  ZeroGPU on *every* request regardless of which text model is chosen, so it is a cost
  both paths carry, not one that's unique to "local." Warm BLIP time is about 6.71s/request
  (see section d), so 150,000 requests x 6.71s is about 280 GPU-hours/month - on a
  dedicated Nvidia T4 (small, $0.40/hour) that's $0.40 x 280 ≈ **about $112/month**.
- **Remote path:** Hugging Face's own routed pricing for `openai/gpt-oss-20b` is
  $0.10 / 1M input tokens and $0.50 / 1M output tokens (other providers on the router
  range from about $0.03 to $0.21 / 1M tokens, so this is a mid-range estimate). Per
  request: 300 x $0.10/1M + 400 x $0.50/1M = $0.00023. At 150,000 requests/month that is
  about $35/month in tokens, **plus the ~$112/month BLIP GPU cost above ≈ $147/month
  total**. Free accounts get $0.10 of monthly inference credit and PRO accounts get
  $2.00 - both are exhausted after roughly 1-9 requests, so at 1,000 users the app would
  run almost entirely on pay-as-you-go token billing past the free credit, not within it.
- **Local path:** no per-request fee, but the compute has to be paid for. Free ZeroGPU
  gives each user a small per-day quota shared across a queue, which 1,000 active users
  would exceed quickly; PRO ($9/month) gives 8x the ZeroGPU quota and priority queueing,
  but is still a shared, rate-limited pool, not a per-request guarantee. To serve this
  volume reliably we would instead size a dedicated GPU: local text generation
  (Qwen3-0.6B) took about 8.0s/request warm, so 150,000 requests x 8.0s is about
  333 GPU-hours/month, plus the ~280 GPU-hours/month BLIP already needs above - together
  about 613 GPU-hours, which still fits inside the ~730 hours/month a single GPU provides
  if left running continuously. A dedicated Nvidia T4 (small, $0.40/hour) run continuously
  costs $0.40 x 24 x 30 = **about $288/month** for both models, regardless of whether
  traffic actually fills that time - Spaces GPU hardware is billed by uptime, not by
  inference-second.
- **Summary:** at this scale the remote path (~$147/month, once BLIP's shared GPU cost is
  counted) is still cheaper than a dedicated GPU running both models continuously
  (~$288/month), but the gap is much smaller than it looks if you only compare the
  text-generation step - BLIP alone is already about a third of the local path's total
  bill. The crossover, where remote's per-request token cost catches up to local's flat
  rate, is around ($288 - $112) / $0.00023 ≈ 765,000 requests/month (~25,500/day) - below
  that, pay-per-token remote inference wins; above it, the flat-rate dedicated GPU becomes
  cheaper. Staying on free ZeroGPU instead of dedicated hardware keeps both paths' GPU
  cost at $0/month, but only works below ZeroGPU's shared per-user quota, which 1,000
  daily-active users would likely exceed.

## f. Comments and concerns

- **Security:** the Space's `HF_TOKEN` and the Discord webhook are stored as repository
  secrets, never in code. Logged-in viewers use their own OAuth token first.
- **Privacy:** in Remote mode the image description (not the image itself) is sent to a
  third-party inference provider. Local-only mode keeps everything on the Space.
- **Reliability and API dependence:** the remote path can fail from rate limits, outages,
  timeouts, or an empty reasoning-model response. Failover to Qwen3 keeps the app working,
  with lower caption quality.
- **Scalability:** ZeroGPU queues requests and limits GPU time per user, so the local path
  would slow down under heavy traffic.
- **Content safety:** the prompt forbids slurs and sexual content, but there is no output
  filter, so an offensive caption is still possible.

## g. Improvement suggestion from an established LLM [LLM only]

**Model:** [ ]

**Prompt:**
> [complete prompt]

**Response:**
> [complete response]

## h. Same prompt, weaker local LLM [LLM only]

**Model:** [ ]

**Response:**
> [complete response]

## i. Comparison of the two responses [Human only]

[ ]

## j. Model choice for real deployment [Human only]

[ ]

---
