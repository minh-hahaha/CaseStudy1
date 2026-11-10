---
title: Meme Creator
colorFrom: purple
colorTo: pink
sdk: gradio
sdk_version: 6.26.0
python_version: '3.12'
app_file: app.py
hf_oauth: true
hf_oauth_scopes:
  - inference-api
pinned: false
short_description: Meme captions from any image, via remote or local LLM.
---

# Meme Creator

- Space: https://huggingface.co/spaces/minh-hahaha/CaseStudy1
- GitHub: https://github.com/minh-hahaha/CaseStudy1
- Demo: https://youtu.be/CZx28BOT-jk
- [CITATIONS.md](documentation/CITATIONS.md)

Meme caption generator for **DS/CS553 Case Study 1**. Upload an image, pick a voice, and get
work-safe captions burned into the image.

## How it works

BLIP describes the image locally, then an LLM writes the captions:

Vision - `Salesforce/blip-image-captioning-base` - Runs Locally  
Captions (remote) - `openai/gpt-oss-20b` - Runs using Hugging Face Inference API  
Captions (local) - `Qwen/Qwen3-0.6B` - Runs Locally (ZeroGPU)

The **Routing** setting picks the path:

- **Auto** (default): remote, falls back to local on any failure
- **Remote only**: no fallback, errors are shown
- **Local only**: no API calls

The status panel shows which model served each request.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export HF_TOKEN=hf_...   # for the remote path
python app.py
```

## Tests

```bash
pip install -r requirements-ci.txt
pytest -q --cov=src
```

Model calls are mocked, so no GPU or downloads are needed.


## Case Study 3: Docker, monitoring and public access

Both products now run as Docker containers on the shared class VM, with Prometheus and
Grafana monitoring them and public tunnels exposing them.

API product - https://jersey-herbs-elf.ngrok-free.dev  
Local product - https://frontier-gbp-foundations-keywords.trycloudflare.com  
Grafana dashboard (read-only, no login) - https://comfortable-guns-graphic-cook.trycloudflare.com/d/group7-meme

The two `trycloudflare.com` URLs change whenever those tunnel containers restart. Run
`./deploy.sh urls` on the VM for the current ones.

### One image, two products

`Dockerfile` builds a single image (CPU-only torch, layers ordered so code edits rebuild in
seconds). The `MEME_PRODUCT` environment variable picks which product a container serves:

api - Remote LLM with failover to local (Auto / Remote only) - Requires HF_Token  
local - BLIP + Qwen3-0.6B only, no API calls - Doesn't Requires HF_Token  
both (default) - Everything, as on the Hugging Face Space - Requires HF_Token

`docker/entrypoint.sh` starts `prometheus-node-exporter` on :9100 in the background, then
runs the app, which serves Gradio on :7860 and its own metrics on :8000.

### Deployment

On the class VM (`ssh -p 2222 group7@melnibone.wpi.edu`), from the repo root:

```bash
./deploy.sh        # build the image and (re)deploy all 7 containers
./deploy.sh urls   # print the current public URLs and container IPs
```

`deploy.sh` prompts for the Hugging Face token, the ngrok authtoken and (first run only) a
Grafana admin password. Nothing secret is written to disk or to the repo. Every container
joins the `group7_net` Docker network, so they reach each other by name, and uses
`--restart unless-stopped`, so nothing depends on an open SSH session.

`group7_api` - `group7/meme-creator-cs3:v3` - VM ports 4700 app, 4704 metrics, 4705 node - API product  
`group7_local` - `group7/meme-creator-cs3:v3` - VM ports 4701 app, 4706 metrics, 4707 node - Local product  
`group7_prometheus` - `prom/prometheus` - VM port 4702 - Scrapes the 4 metric endpoints  
`group7_grafana` - `grafana/grafana` - VM port 4703 - Dashboards, anonymous read-only viewing  
`group7_ngrok_api` - `ngrok/ngrok` - Public URL for the API product  
`group7_cf_local` - `cloudflare/cloudflared` - Public URL for the local product  
`group7_cf_grafana` - `cloudflare/cloudflared` - Public URL for Grafana  

Ports 4700-4709 are group 7's claimed range on the shared VM. Inside the containers the
standard ports (7860, 8000, 9100, 9090, 3000) are used, and Prometheus scrapes them by
container name over `group7_net`, never through the VM ports.

To look at anything privately from a laptop, tunnel the VM ports over SSH:

```bash
ssh -N -L 7860:localhost:4700 -L 7861:localhost:4701 -L 9090:localhost:4702 \
    -L 3000:localhost:4703 -p 2222 group7@melnibone.wpi.edu
```

### Monitoring

**Node exporter** (`:9100`, installed in the image): CPU, memory, disk and network.

**App metrics** (`:8000`, `src/metrics.py`, via `prometheus_client`):

`meme_requests_total{action, status}` - Counter - Button clicks by action (generate, reroll, render, style_gallery) and outcome (ok, failed, error)  
`meme_inflight_requests` - Gauge - Requests being processed right now  
`meme_vision_seconds` - Histogram - Time for local BLIP to describe an image  
`meme_caption_seconds{path, outcome}` - Histogram - Caption generation time on the remote or local path  
`meme_caption_source_total{path}` - Counter - Which path actually produced the captions  
`meme_failovers_total` - Counter - Remote API failures served by the local model instead  
`meme_captions_returned_total` - Counter - Captions handed back to users  
`meme_image_megapixels` - Histogram - Size of uploaded images, which drives BLIP time and memory  

**Prometheus** (`monitoring/prometheus.yml`) scrapes four jobs every 15 s: `api_app`,
`api_node`, `local_app` and `local_node`.

**Grafana** (`monitoring/grafana_dashboard.json`) has 9 panels: request rate, failed
requests, in-flight requests, p95 caption latency by path, p95 BLIP latency, remote vs
local captions, failovers, CPU and memory. To recreate it: add a Prometheus data source
with URL `http://group7_prometheus:9090`, then Dashboards → New → Import and upload the
JSON.

### Public access

- **API product: ngrok.** The free plan gives one fixed domain per account. A second
  ngrok tunnel on the same account joined the same domain and split traffic between the
  two apps, so only one product uses ngrok.
- **Local product and Grafana: Cloudflare quick tunnels** (no account needed). The VM's
  network blocks QUIC, cloudflared's default transport, which shows up as
  `failed to dial a quic connection` in the logs and Cloudflare error 1033 in the browser.
  `--protocol http2` fixes it.
- All three tunnels run as containers rather than background shell jobs, which died when
  the SSH session ended.

### Operational notes

- **Node exporter numbers are VM-wide.** Inside a container it reports the whole shared
  VM (64 GB RAM, every group's workload), so `api_node` and `local_node` show nearly the
  same CPU and memory. Per-container numbers would need cAdvisor or `docker stats`.
- **Remote quota.** When the Hugging Face account runs out of Inference credits, the
  remote path returns `402 Payment Required`. In Auto mode the app fails over to the local
  model, so users still get captions, and `meme_failovers_total` records each case.
- **Grafana's first start is slow.** On a fresh data volume it runs about 800 database
  migrations, which took around 10 minutes on the shared disk. Later restarts are fast.
- **Updating the app:** `git pull` on the VM, then `./deploy.sh`. Only the app layers
  rebuild, but every container is replaced, so the Cloudflare URLs change.

### Files added for Case Study 3

`Dockerfile`, `.dockerignore`, `requirements-docker.txt` - The container image  
`docker/entrypoint.sh` - Starts the node exporter, then the app  
`src/metrics.py`, `tests/test_metrics.py` - App metrics and their tests  
`deploy.sh` - Builds and deploys the full stack on the VM  
`monitoring/prometheus.yml` - Prometheus scrape config  
`monitoring/grafana_dashboard.json` - Grafana dashboard  
