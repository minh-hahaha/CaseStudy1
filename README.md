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

| Step | Model | Runs |
|---|---|---|
| Vision | `Salesforce/blip-image-captioning-base` | Local |
| Captions (remote) | `openai/gpt-oss-20b` | Hugging Face Inference API |
| Captions (local) | `Qwen/Qwen3-0.6B` | Local (ZeroGPU) |

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


## Case Study 3: Docker deployment and monitoring

On the class VM, from the repo root:

```bash
./deploy.sh        # build the image and (re)deploy all 7 containers
./deploy.sh urls   # print the current public URLs and container IPs
```

`deploy.sh` prompts for the Hugging Face token, the ngrok authtoken and (first run only)
a Grafana admin password. It runs the two products, Prometheus, Grafana and three tunnels
on the `group7_net` Docker network, using VM ports 4700-4707.

- `monitoring/prometheus.yml`: scrapes app metrics (:8000) and node exporters (:9100)
- `monitoring/grafana_dashboard.json`: 9-panel dashboard; import it in Grafana
  (Dashboards → New → Import) and pick the Prometheus data source
  (`http://group7_prometheus:9090`)
