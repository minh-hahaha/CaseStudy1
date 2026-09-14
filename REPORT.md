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

**Purpose:** make a fast, on-topic, workplace-safe meme without writing the joke yourself.

**Target audience:** professors, TAs, and presenters who open a lecture or meeting with a
meme, and students making slides.

<!-- The app offers two generation paths inside one interface. The **Meme Factory** tab makes
memes. The **Model Lab** tab runs the remote and local models side by side on the same
image and prompt, to compare speed and quality. A **Routing** setting selects *Auto* (remote
first, automatic failover to local), *Remote only*, or *Local only* (no API calls). The
status panel always names the model that served the request. -->

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
here is to turn pixels into text so a text-only LLM can joke about the image.

**gpt-oss-20b.** OpenAI's open-weight reasoning model: a mixture-of-experts transformer with
about 21B total parameters, of which about 3.6B are active per token. It is served remotely
through `huggingface_hub.InferenceClient` with low reasoning effort. OpenAI has not released
its training dataset.

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
| BLIP vision time | [ ]s | [ ]s |
| Caption generation time | [ ]s | [ ]s |
| First request after idle (cold start) | [ ]s | [ ]s |
| Captions usable / requested | [ ] / [ ] | [ ] / [ ] |
| Host resources | Network only | ZeroGPU slice, ~[ ] GB model |

*[Observations: speed, caption quality, how often each follows the style and JSON format.]*

## e. Cost analysis (1,000 users)

*[Fill in from https://huggingface.co/pricing. Assumption to state: e.g. 1,000 users x 5
requests per day.]*

- **Remote path:** Inference API cost per request [ ] x [ ] requests = [ ] per month.
  Free and PRO accounts have monthly inference credits and rate limits, so at 1,000 users
  the app would need [ ].
- **Local path:** no per-request fee, but the Space hardware is paid for continuously.
  ZeroGPU requires PRO ([ ]/month) and has per-user GPU quotas; dedicated GPU hardware
  costs [ ]/hour, about [ ]/month.
- **Summary:** [which is cheaper at this scale, and where the crossover point is].

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

*LLM assistance: Claude Opus 5 (via Claude Code) helped draft sections b, c, and f of this
report. See CITATIONS.md.*
