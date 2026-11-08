FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 0. System packages: node exporter for container metrics on :9100.
RUN apt-get update \
&& apt-get install -y --no-install-recommends prometheus-node-exporter \
&& rm -rf /var/lib/apt/lists/*

# 1. CPU-only torch first: biggest dependency, changes least often.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

WORKDIR /opt/app

# 2. Python deps. Copy ONLY the requirements file first, so editing app code
#    doesn't invalidate this layer.
COPY requirements-docker.txt .
RUN pip install -r requirements-docker.txt

# 3. App code last: it changes on every deploy.
COPY app.py ./
COPY src ./src
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

ENV GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    HF_HOME=/opt/hf-cache \
    MEME_PRODUCT=both

EXPOSE 7860 9100

ENTRYPOINT ["sh", "/usr/local/bin/entrypoint.sh"]