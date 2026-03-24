#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${1:-writerdeck.local}"
PI_USER="${2:-pi}"
REMOTE_DIR="~/writer-deck"

echo "Deploying to ${PI_USER}@${PI_HOST}:${REMOTE_DIR} ..."

rsync -avz --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.venv' \
    --exclude 'venv' \
    --exclude 'lib/waveshare_epd' \
    --exclude 'htmlcov' \
    --exclude '.coverage' \
    --exclude '.DS_Store' \
    --exclude 'config.yaml' \
    ./ "${PI_USER}@${PI_HOST}:${REMOTE_DIR}/"

echo "Restarting writer-deck service ..."
ssh "${PI_USER}@${PI_HOST}" 'sudo systemctl restart writer-deck'

echo "Deploy complete. Tailing logs (Ctrl+C to stop) ..."
ssh "${PI_USER}@${PI_HOST}" 'journalctl -u writer-deck -f --no-pager -n 20'
