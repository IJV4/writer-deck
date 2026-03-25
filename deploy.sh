#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${1:-writerdeck.local}"
PI_USER="${2:-pi}"
REMOTE_DIR="~/writer-deck"

echo "Deploying to ${PI_USER}@${PI_HOST}:${REMOTE_DIR} ..."

rsync -avz --delete \
    --exclude '.git' \
    --exclude '.claude' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.Zone.Identifier' \
    --exclude '.venv' \
    --exclude 'venv' \
    --exclude 'htmlcov' \
    --exclude '.coverage' \
    --exclude '.pytest_cache' \
    --exclude '.DS_Store' \
    --exclude 'config.yaml' \
    --exclude 'tests/' \
    --exclude 'requirements-dev.txt' \
    --exclude 'setup-dev.sh' \
    --exclude 'deploy.sh' \
    --exclude 'pyproject.toml' \
    --exclude '*.md' \
    ./ "${PI_USER}@${PI_HOST}:${REMOTE_DIR}/"

echo "Restarting writer-deck service (if installed) ..."
ssh "${PI_USER}@${PI_HOST}" \
    'systemctl is-active --quiet writer-deck && sudo systemctl restart writer-deck || echo "  Service not yet installed — run setup.sh on the Pi first."'

echo "Done."
