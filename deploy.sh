#!/usr/bin/env bash
# Case Study 3 (group 7): build and (re)deploy the full stack on the class VM.
#
#   group7_api          API product        VM 4700 -> 7860, 4704 -> 8000, 4705 -> 9100
#   group7_local        local product      VM 4701 -> 7860, 4706 -> 8000, 4707 -> 9100
#   group7_prometheus   scrapes the four metric endpoints          VM 4702 -> 9090
#   group7_grafana      dashboards, anonymous read-only viewing    VM 4703 -> 3000
#   group7_ngrok_api    public URL for the API product (ngrok)
#   group7_cf_local     public URL for the local product (Cloudflare quick tunnel)
#   group7_cf_grafana   public URL for Grafana (Cloudflare quick tunnel)
#
# Every container joins group7_net, so they reach each other by name, and uses
# --restart unless-stopped, so nothing depends on anyone's SSH session.
# VM ports are bound to 127.0.0.1: the public way in is the tunnels.
#
# Usage, from the repo root on the VM:
#   ./deploy.sh            rebuild the image and redeploy everything
#   ./deploy.sh urls       just print the current public URLs
#
# Secrets come from the environment, or are prompted for (input hidden):
#   HF_TOKEN               Hugging Face token with Inference permission (API product)
#   NGROK_AUTHTOKEN        ngrok authtoken
#   GF_ADMIN_PASSWORD      Grafana admin password; only used the first time the
#                          group7_grafana_data volume is created
set -euo pipefail

IMAGE="group7/meme-creator-cs3:v3"
NET="group7_net"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROM_CONFIG="$REPO_DIR/monitoring/prometheus.yml"

print_urls() {
    local ngrok_url local_url grafana_url
    ngrok_url=$(docker logs group7_ngrok_api 2>&1 | grep -o 'url=https://[^ ]*' | tail -1 | cut -d= -f2)
    local_url=$(docker logs group7_cf_local 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
    grafana_url=$(docker logs group7_cf_grafana 2>&1 | grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' | tail -1)
    echo "API product:    ${ngrok_url:-<not found yet>}"
    echo "Local product:  ${local_url:-<not found yet>}"
    echo "Grafana:        ${grafana_url:+$grafana_url/d/group7-meme}"
    echo
    for c in group7_api group7_local; do
        echo "$c IP: $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$c")"
    done
}

if [[ "${1:-}" == "urls" ]]; then
    print_urls
    exit 0
fi

# Prompt for each secret on its own line, so pasting never feeds a secret
# prompt the next command by mistake.
ask_secret() {
    local var="$1" prompt="$2"
    if [[ -z "${!var:-}" ]]; then
        read -rsp "$prompt: " "${var?}" || true
        echo
    fi
    if [[ -z "${!var:-}" ]]; then
        echo "error: $var is empty" >&2
        exit 1
    fi
    export "${var?}"
}
ask_secret HF_TOKEN "Hugging Face token"
ask_secret NGROK_AUTHTOKEN "ngrok authtoken"
if ! docker volume inspect group7_grafana_data >/dev/null 2>&1; then
    ask_secret GF_ADMIN_PASSWORD "New Grafana admin password"
fi

echo "==> Building $IMAGE"
docker build -t "$IMAGE" "$REPO_DIR"

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"

# Replace a container with a fresh one: run NAME [docker run args...]
run() {
    local name="$1"
    shift
    docker rm -f "$name" >/dev/null 2>&1 || true
    docker run -d --name "$name" --network "$NET" --restart unless-stopped "$@" >/dev/null
    echo "    started $name"
}

echo "==> Products"
run group7_api \
    -p 127.0.0.1:4700:7860 -p 127.0.0.1:4704:8000 -p 127.0.0.1:4705:9100 \
    -v group7_hf_cache:/opt/hf-cache -e MEME_PRODUCT=api -e HF_TOKEN \
    "$IMAGE"
run group7_local \
    -p 127.0.0.1:4701:7860 -p 127.0.0.1:4706:8000 -p 127.0.0.1:4707:9100 \
    -v group7_hf_cache:/opt/hf-cache -e MEME_PRODUCT=local \
    "$IMAGE"

echo "==> Monitoring"
run group7_prometheus \
    -p 127.0.0.1:4702:9090 \
    -v "$PROM_CONFIG":/etc/prometheus/prometheus.yml:ro \
    prom/prometheus
# Grafana only reads the admin password when it first creates its database,
# so pass it only when one was given.
grafana_pw=()
if [[ -n "${GF_ADMIN_PASSWORD:-}" ]]; then
    grafana_pw=(-e GF_SECURITY_ADMIN_PASSWORD="$GF_ADMIN_PASSWORD")
fi
run group7_grafana \
    -p 127.0.0.1:4703:3000 \
    -v group7_grafana_data:/var/lib/grafana \
    "${grafana_pw[@]}" \
    -e GF_AUTH_ANONYMOUS_ENABLED=true -e GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer \
    grafana/grafana

echo "==> Public tunnels"
# ngrok's free plan has one fixed domain per account, so only one product goes
# through ngrok. The VM's network blocks QUIC, so cloudflared must use http2.
run group7_ngrok_api \
    -e NGROK_AUTHTOKEN \
    ngrok/ngrok:latest http http://group7_api:7860 --log stdout
run group7_cf_local \
    cloudflare/cloudflared:latest tunnel --no-autoupdate --protocol http2 \
    --url http://group7_local:7860
run group7_cf_grafana \
    cloudflare/cloudflared:latest tunnel --no-autoupdate --protocol http2 \
    --url http://group7_grafana:3000

echo "==> Waiting for tunnels to register"
sleep 20
print_urls
echo
echo "Cloudflare URLs change every time those containers restart: update the"
echo "Google Sheet with the URLs above. Grafana may take several minutes to answer"
echo "the first time its data volume is created."
