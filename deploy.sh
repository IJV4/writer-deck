#!/usr/bin/env bash
# Writer Deck — atomic, revertible deploy over SSH (OPS-1).
#
# Instead of mutating the live tree in place (the old `rsync --delete`, which left
# partial code on a mid-sync failure and had no rollback), this deploys into a
# fresh timestamped release dir on the Pi and atomically swaps a `current`
# symlink. The systemd unit's WorkingDirectory/ExecStart/ExecStopPost all point at
# `current` (rendered by setup.sh from writer-deck.service), so the swap + restart
# switches code atomically and a rollback is a one-line symlink repoint.
#
# Remote layout (must match setup.sh):
#   <BASE_DIR>/
#     releases/<ts>/          a deployed release (this script rsyncs code here)
#     releases/<ts>/venv ->   <BASE_DIR>/venv   (shared venv, symlinked per release)
#     venv/                    the ONE shared virtualenv (created by setup.sh)
#     current -> releases/<ts> the active release
#
# Usage:
#   ./deploy.sh [PI_HOST] [PI_USER]
#   ./deploy.sh --rollback [PI_HOST] [PI_USER]     # revert to previous release
#   ./deploy.sh --list     [PI_HOST] [PI_USER]     # list releases + current
set -euo pipefail

# --- args ------------------------------------------------------------------
ACTION="deploy"
case "${1:-}" in
    --rollback) ACTION="rollback"; shift ;;
    --list)     ACTION="list";     shift ;;
    --help|-h)  ACTION="help";     shift ;;
esac

PI_HOST="${1:-writer-deck.local}"
PI_USER="${2:-pi}"

# Remote base dir. Matches the README/setup.sh clone location (~/writer-deck).
# NOTE: paths are expanded on the REMOTE side; keep them as ~ / $HOME in SSH calls.
RELEASES_SUBDIR='writer-deck/releases'      # relative to remote $HOME
KEEP_RELEASES=5                             # prune: keep this many newest releases
SSH_TARGET="${PI_USER}@${PI_HOST}"

if [ "$ACTION" = "help" ]; then
    sed -n '2,30p' "$0"
    exit 0
fi

# --- list ------------------------------------------------------------------
if [ "$ACTION" = "list" ]; then
    echo "Releases on ${SSH_TARGET}:"
    ssh "$SSH_TARGET" bash -s <<'REMOTE'
set -euo pipefail
BASE="$HOME/writer-deck"
if [ -d "$BASE/releases" ]; then
    ls -1 "$BASE/releases" | sort
else
    echo "  (no releases dir yet — run setup.sh on the Pi first)"
fi
if [ -L "$BASE/current" ]; then
    echo "current -> $(readlink "$BASE/current")"
else
    echo "current -> (not set)"
fi
REMOTE
    exit 0
fi

# --- rollback --------------------------------------------------------------
# Repoint `current` at the previous release (the newest one that is NOT current)
# and restart the service. Only ever moves the `current` symlink — never deletes.
if [ "$ACTION" = "rollback" ]; then
    echo "Rolling back on ${SSH_TARGET} ..."
    ssh "$SSH_TARGET" bash -s <<'REMOTE'
set -euo pipefail
BASE="$HOME/writer-deck"
RELEASES="$BASE/releases"
CURRENT="$BASE/current"
[ -L "$CURRENT" ] || { echo "  ERROR: $CURRENT is not a symlink; cannot roll back." >&2; exit 1; }
cur="$(basename "$(readlink "$CURRENT")")"
# Newest release that is not the current one, by the trailing YYYYMMDD-HHMMSS
# timestamp embedded in the name — NOT a lexical name sort (breaks on the
# one-time setup.sh release named "setup-<ts>": "s" > "2" sorts it last) and
# NOT directory mtime (running the app writes __pycache__ into the release
# dir, which bumps mtime on every restart regardless of how old the release
# actually is). Every release name, with or without a prefix, ends in exactly
# 15 characters of YYYYMMDD-HHMMSS, so that suffix alone is the sort key.
prev="$(
    ls -1 "$RELEASES" | grep -vxF "$cur" | while IFS= read -r d; do
        printf '%s %s\n' "${d: -15}" "$d"
    done | sort | tail -n1 | cut -d' ' -f2-
)"
[ -n "$prev" ] || { echo "  ERROR: no previous release to roll back to (only '$cur')." >&2; exit 1; }
echo "  current: $cur  ->  rolling back to: $prev"
ln -sfn "$RELEASES/$prev" "$CURRENT.tmp"
mv -Tf "$CURRENT.tmp" "$CURRENT"
echo "  current -> $(readlink "$CURRENT")"
if systemctl is-active --quiet writer-deck; then
    sudo systemctl restart writer-deck
    echo "  service restarted."
else
    echo "  service not active — start it with: sudo systemctl start writer-deck"
fi
REMOTE
    echo "Rollback done."
    exit 0
fi

# --- deploy ----------------------------------------------------------------
TS="$(date +%Y%m%d-%H%M%S)"

echo "Deploying to ${SSH_TARGET} -> releases/${TS} ..."

# 1. Ensure the release dir exists remotely (does NOT touch data dirs).
ssh "$SSH_TARGET" "mkdir -p ~/${RELEASES_SUBDIR}/${TS}"

# 2. rsync code into the FRESH release dir. No --delete: the target is a new empty
#    dir, so nothing pre-existing can be removed. The --exclude list is preserved
#    verbatim from the old deploy so data/dev files are never copied. config.yaml,
#    ~/Documents, ~/.config live OUTSIDE the release tree and are never touched.
rsync -avz \
    --exclude '.git' \
    --exclude '.claude' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*:Zone.Identifier' \
    --exclude '.venv' \
    --exclude 'venv' \
    --exclude 'releases' \
    --exclude 'current' \
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
    ./ "${SSH_TARGET}:~/${RELEASES_SUBDIR}/${TS}/"

# 3. On the Pi: symlink the shared venv into the release, atomically swap `current`,
#    restart the service, and prune old releases. All quoting/logic runs remotely.
#    TS is passed as $1; KEEP as $2 so no host var leaks into the remote script.
ssh "$SSH_TARGET" bash -s -- "$TS" "$KEEP_RELEASES" <<'REMOTE'
set -euo pipefail
TS="$1"
KEEP="$2"
BASE="$HOME/writer-deck"
RELEASES="$BASE/releases"
RELEASE="$RELEASES/$TS"
CURRENT="$BASE/current"
SHARED_VENV="$BASE/venv"

[ -d "$RELEASE" ] || { echo "  ERROR: release $RELEASE missing after rsync." >&2; exit 1; }

# Shared venv must exist (created by setup.sh). Symlink it into the new release.
if [ ! -d "$SHARED_VENV" ]; then
    echo "  ERROR: shared venv $SHARED_VENV not found — run setup.sh on the Pi first." >&2
    exit 1
fi
ln -sfn "$SHARED_VENV" "$RELEASE/venv.tmp"
mv -Tf "$RELEASE/venv.tmp" "$RELEASE/venv"

# Symlink the release's config.yaml at the persistent one in $BASE (same reason as
# venv above): config.py resolves config.yaml relative to its own file inside the
# release, and this rsync excludes config.yaml (step 2) so a deploy never
# overwrites the user's config — that only works if every release points back at
# the same persistent file. Optional: skip if the Pi has no config.yaml yet.
CONFIG_YAML="$BASE/config.yaml"
if [ -e "$CONFIG_YAML" ]; then
    if [ -e "$RELEASE/config.yaml" ] && [ ! -L "$RELEASE/config.yaml" ]; then
        echo "  ERROR: $RELEASE/config.yaml exists and is not a symlink; refusing to touch it." >&2
        exit 1
    fi
    ln -sfn "$CONFIG_YAML" "$RELEASE/config.yaml.tmp"
    mv -Tf "$RELEASE/config.yaml.tmp" "$RELEASE/config.yaml"
fi

# Atomic swap of the `current` symlink (ln to a temp name, then rename over).
if [ -e "$CURRENT" ] && [ ! -L "$CURRENT" ]; then
    echo "  ERROR: $CURRENT exists and is not a symlink; refusing to swap." >&2
    exit 1
fi
ln -sfn "$RELEASE" "$CURRENT.tmp"
mv -Tf "$CURRENT.tmp" "$CURRENT"
echo "  current -> $(readlink "$CURRENT")"

# Restart the service (unit points at $CURRENT, so it now runs the new code).
if systemctl is-active --quiet writer-deck; then
    sudo systemctl restart writer-deck
    echo "  service restarted."
else
    echo "  Service not active — run setup.sh on the Pi, then: sudo systemctl start writer-deck"
fi

# Prune: keep the $KEEP newest release dirs, remove older ones. SAFETY: this only
# ever operates on entries directly under $RELEASES, never data dirs, and never the
# active release (it's among the newest kept, and is skipped explicitly). `rm -rf`
# is intentionally NOT used; we delete each stale release dir individually and
# refuse anything that is not directly under RELEASES. Portable: no `mapfile` and
# no `head -n -N` (works on GNU and BSD userlands alike).
if [ -d "$RELEASES" ]; then
    cur_name="$(basename "$(readlink "$CURRENT")")"
    total="$(ls -1 "$RELEASES" | wc -l | tr -d ' ')"
    if [ "$total" -gt "$KEEP" ]; then
        drop=$(( total - KEEP ))          # number of oldest releases to remove
        i=0
        # Oldest-first (sort ascending): the first $drop are the stale ones.
        ls -1 "$RELEASES" | sort | while IFS= read -r name; do
            i=$(( i + 1 ))
            [ "$i" -le "$drop" ] || break
            [ -n "$name" ] || continue
            [ "$name" = "$cur_name" ] && continue      # never delete the active release
            target="$RELEASES/$name"
            case "$target" in
                "$RELEASES"/*) ;;                       # must be directly under releases/
                *) echo "  refusing to prune unexpected path: $target" >&2; continue ;;
            esac
            [ -d "$target" ] || continue
            rm -r -- "$target"
            echo "  pruned old release: $name"
        done
    fi
fi
REMOTE

echo "Done. Deployed release ${TS} and swapped current."
echo "Roll back with: ./deploy.sh --rollback ${PI_HOST} ${PI_USER}"
