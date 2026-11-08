#!/bin/sh
# Start node exporter in the background on its standard port, then run the app.
# `exec` makes Python the main process, so `docker stop` reaches it directly.
set -e

prometheus-node-exporter --web.listen-address=":9100" &

exec python /opt/app/app.py