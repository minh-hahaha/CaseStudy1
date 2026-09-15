# Meme Creator: Case Study 1 Report

**Hugging Face Space:** https://huggingface.co/spaces/minh-hahaha/CaseStudy1
**GitHub:** https://github.com/minh-hahaha/CaseStudy1

## a. Members

- Minh Ha
- Max Jeronimo

*Note: We did this most of the project together in-person, pair programming, so most of the commits come under Minh (with Claude Code's help of course).*

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
  secrets, never in code. Logged-in viewers use their own OAuth token.
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

**Model:** [ Claude Opus 5 High Effort]

**Prompt:**
My partner and I built a meme-generator app called Meme Creator. A user uploads a photo, picks a "voice" (e.g. Professor Energy, Dad Joke, Corporate LinkedIn), optionally adds a topic (e.g. "midterm week"), and the app runs BLIP image captioning locally, then sends the description to an LLM (gpt-oss-20b remotely, or Qwen3-0.6B locally as fallback) to generate a caption, which is rendered onto the image in classic top/bottom meme style. What would you improve about this product, its architecture, or its user experience?

**Response:**
The biggest lever is the BLIP stage, and it's worth being blunt about it: BLIP captions are the enemy of comedy. It gives you "a man sitting at a desk with a laptop" when the joke actually lives in the fact that his eyes are dead, there's a Monster can in frame, and it's clearly 3am. Your LLM never sees any of that. It's writing jokes about a sentence, not about a photo.

Two ways out, in order of how much I'd recommend them:

Replace the two-stage pipeline with a VLM. Qwen2.5-VL-7B, Moondream2, or a hosted multimodal endpoint takes the image directly and writes the caption in one pass. This collapses your architecture, removes an entire failure mode, and the quality jump will be larger than anything else on this list.

If you keep BLIP, interrogate it instead of captioning with it. Use BLIP-2 in VQA mode and ask three or four targeted questions: what's the facial expression, what's out of place, what's the setting, how many people. Assemble those into a scene description. You can also run CLIP zero-shot over a small set of meme-relevant axes (tired / smug / chaotic / wholesome). It's a hack, but it recovers a lot of the signal you're currently throwing away.

The fallback cliff

gpt-oss-20b to Qwen3-0.6B is not a graceful degradation, it's a trapdoor. A 0.6B model will produce captions that are technically English and reliably unfunny, and the user has no idea why the app suddenly got worse. Three options: bump the local tier to a quantized 3B or 4B, fall back to template-based captions per voice (fill-in-the-blank structures are more dependably funny than a tiny model improvising), or at minimum surface the tier so the user knows they're on the backup and can retry.

Cheapest quality win available

Generate five captions, not one. Humor has enormous variance, and sampling at temperature ~1.0 and showing the user a few options converts a coin flip into a near-certain hit. Users are also much more forgiving of a bad option in a set of five than of one bad output. Pair this with a regenerate button and per-line editing, because nobody ships the first caption they see.

Make the scene description editable

This is the highest value UX fix. When the vision stage misreads the photo, every downstream caption is nonsense and the user has no recourse except reuploading. If you show the description in a small editable field ("I see: a dog wearing sunglasses on a couch") the user fixes it in four seconds and gets a working meme. It also doubles as free labeled data on where your captioner fails.

Make voices real

Right now a voice is probably a line in a system prompt. Turn each one into a bundle: persona instruction, three or four few-shot examples, a length constraint, and a forbidden-phrases list. Few-shot examples are what actually pin down voice in smaller models, and they'll fix the drift where Corporate LinkedIn and Professor Energy start sounding identical after a few generations. Longer term, user-created voices are the obvious growth feature.

Output contract

Ask for JSON with top and bottom fields and hard word caps, then validate and retry on violation. Free-text parsing plus an LLM that decided to write a paragraph equals broken layout. On the rendering side: auto-fit font size, wrap properly, and run face detection so text doesn't land on the subject's face. Also consider offering the modern format (white caption box above the image) alongside classic Impact overlay, since that's what actually circulates on social now.

Infrastructure

Cache the BLIP or VLM output keyed on an image hash so regeneration skips the vision pass entirely. Preload models at startup rather than on first request. Stream progress per stage, because a multi-second pipeline with a spinner feels broken.

The thing you have to handle before this goes public

Users uploading photos of real people plus an LLM writing jokes about them is a harassment vector, and an open image upload endpoint carries real content moderation obligations. At minimum: an NSFW image classifier on upload, a caption filter on output, and a policy on photos of identifiable people. This is unglamorous and it's the part that gets a project shut down.

One thing worth building for your own sake

Given where you're headed, log thumbs up and down per generation along with the voice, model tier, and scene description. Within a few hundred samples you have a preference dataset, an eval set for pairwise LLM-as-judge comparisons, and concrete evidence of which voices and which model tiers actually work. "I built an eval harness for a subjective generation task" is a much stronger story than "I built a meme app."

## h. Same prompt, weaker local LLM [LLM only]

**Model:** [Qwen 3-0.6B ]

**Response:**
Here are potential improvements to your Meme Creator app, focusing on product features, architecture optimization, and user experience:

Product Features
Voice-to-Text Integration

Add a voice-to-text feature to allow users to input their voice (e.g., "Dad Joke") directly into the app, enabling seamless voice input for captions.
Integrate with a voice recognition library (e.g., Google Speech-to-Text) to capture audio and generate text.
Topic Customization

Offer a dropdown menu or a search bar to allow users to select a topic (e.g., "midterm week", "career transition") before generating the meme.
Include a "Save & Share" button to save the generated caption and topic for future use.
Multilingual Support

Add support for multiple languages (e.g., English, Spanish, French) to cater to a broader user base.
Architecture Optimization
Efficient Model Selection

Optimize the BLIP model for faster inference (e.g., use a more efficient pre-trained model or a hybrid architecture).
Implement a fallback mechanism for LLMs (e.g., Qwen3-0.6B) if BLIP fails to produce a caption, ensuring reliability.
Scalable Infrastructure

Use a cloud-based model (e.g., AWS, Azure) for LLMs to ensure scalability and reduce latency.
Integrate with a serverless architecture for automatic scaling based on user traffic.
Real-Time Processing

Improve BLIP performance by using a more optimized model or parallel processing for faster image captioning.
User Experience
Intuitive Interface

Design a clean, drag-and-drop interface for uploading the photo and selecting the voice and topic.
Include a "Start" button to immediately generate the meme.
Enhanced Voice Selection

Allow users to choose a voice (e.g., "Professor Energy", "Dad Joke") and adjust the caption dynamically.
Add a voice-to-text feature to capture and generate captions directly from voice.
Responsive Design

Ensure the app works seamlessly on mobile and desktop, with a responsive layout.
By refining these areas, the app can become more versatile, efficient, and user-friendly.

## i. Comparison of the two responses [Human only]

[ ]

## j. Model choice for real deployment [Human only]

[ ]

---
