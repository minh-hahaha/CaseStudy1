#!/usr/bin/env bash
set -euo pipefail
set -a; . "$HOME/.cs553.env"; set +a
cd "$HOME/CaseStudy1"
exec "$HOME/venv/bin/python" app.py