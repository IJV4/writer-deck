#!/usr/bin/env bash
# Writer Deck — one-shot setup script for Raspberry Pi Zero 2 W
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# OPS-1: release layout. The systemd unit points WorkingDirectory/ExecStart at a
# `current` symlink so deploy.sh can atomically swap releases and roll back.
#   <BASE_DIR>/
#     releases/<ts>/   <- an individual release (bootstrapped here / added by deploy.sh)
#     releases/<ts>/venv -> <BASE_DIR>/venv   (shared venv, symlinked per release)
#     venv/            <- the ONE shared virtualenv (survives rollbacks)
#     current          -> releases/<ts>       (the active release; atomic swap target)
#
# setup.sh may be run either from an existing release dir (its parent is
# <BASE_DIR>/releases) or from a plain clone (e.g. ~/writer-deck). In the clone
# case we bootstrap the clone's own code into a first release under releases/ so
# the running service never points at the mutable clone. deploy.sh reuses the SAME
# BASE_DIR and RELEASES_DIR. Keep this layout in sync with deploy.sh.
if [ "$(basename "$(dirname "$SCRIPT_DIR")")" = "releases" ]; then
    # Already inside <BASE_DIR>/releases/<ts>.
    BASE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
    RELEASE_DIR="$SCRIPT_DIR"
    BOOTSTRAP=0
else
    # Plain clone: this dir is the base; bootstrap its code into a first release.
    BASE_DIR="$SCRIPT_DIR"
    RELEASE_DIR="$BASE_DIR/releases/setup-$(date +%Y%m%d-%H%M%S)"
    BOOTSTRAP=1
fi
# BASE_DIR mirrors deploy.sh — keep the release layout in sync between the two.
CURRENT_LINK="$BASE_DIR/current"
SHARED_VENV="$BASE_DIR/venv"

echo "=== Writer Deck Setup ==="

# 1. System packages
echo "[1/11] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-dev python3-venv python3-pip \
    libfreetype6-dev libjpeg-dev libopenjp2-7-dev \
    libgpiod-dev git evtest \
    avahi-daemon libnss-mdns \
    fonts-hack-ttf fonts-liberation fonts-courier-prime fonts-ebgaramond \
    fonts-lato fonts-dejavu-core

# 2. Set hostname for mDNS discovery
echo "[2/11] Configuring hostname (writer-deck.local)..."
sudo hostnamectl set-hostname writer-deck
if ! grep -q "127.0.1.1.*writer-deck" /etc/hosts 2>/dev/null; then
    sudo sed -i 's/127.0.1.1.*/127.0.1.1\twriter-deck/' /etc/hosts
fi
sudo systemctl enable --now avahi-daemon

# 3. Enable SPI + I2C, disable Bluetooth
echo "[3/11] Configuring boot options..."
BOOT_CONFIG="/boot/config.txt"
[ -f "/boot/firmware/config.txt" ] && BOOT_CONFIG="/boot/firmware/config.txt"

sudo grep -q "^dtparam=spi=on" "$BOOT_CONFIG" 2>/dev/null || \
    echo "dtparam=spi=on" | sudo tee -a "$BOOT_CONFIG" > /dev/null
sudo grep -q "^dtparam=i2c_arm=on" "$BOOT_CONFIG" 2>/dev/null || \
    echo "dtparam=i2c_arm=on" | sudo tee -a "$BOOT_CONFIG" > /dev/null
sudo grep -q "^dtoverlay=disable-bt" "$BOOT_CONFIG" 2>/dev/null || \
    echo "dtoverlay=disable-bt" | sudo tee -a "$BOOT_CONFIG" > /dev/null
# FAULT-4: enable the bcm2835 hardware watchdog so a kernel/hard hang forces a
# reboot (boot-time init()+Clear() then restores the panel). Paired with
# RuntimeWatchdogSec below in /etc/systemd/system.conf.
sudo grep -q "^dtparam=watchdog=on" "$BOOT_CONFIG" 2>/dev/null || \
    echo "dtparam=watchdog=on" | sudo tee -a "$BOOT_CONFIG" > /dev/null

# FAULT-4: tell systemd to pet the hardware watchdog. RuntimeWatchdogSec must be
# <= ~15s (the bcm2835 max timeout); if systemd hangs, the SoC reboots the Pi.
# Idempotent: rewrite an existing (possibly commented) key, else append it.
SYSTEMD_CONF="/etc/systemd/system.conf"
if grep -qE "^RuntimeWatchdogSec=14$" "$SYSTEMD_CONF" 2>/dev/null; then
    :  # already set to the desired value
elif grep -qE "^#?RuntimeWatchdogSec=" "$SYSTEMD_CONF" 2>/dev/null; then
    sudo sed -i -E "s|^#?RuntimeWatchdogSec=.*|RuntimeWatchdogSec=14|" "$SYSTEMD_CONF"
else
    echo "RuntimeWatchdogSec=14" | sudo tee -a "$SYSTEMD_CONF" > /dev/null
fi

# 4. Disable HDMI to save power
echo "[4/11] Disabling HDMI output..."
if ! grep -q "tvservice -o" /etc/rc.local 2>/dev/null; then
    sudo sed -i 's|^exit 0|/usr/bin/tvservice -o\nexit 0|' /etc/rc.local 2>/dev/null || true
fi

# 5. Install lgpio (required on Bookworm)
echo "[5/11] Installing lgpio..."
if ! python3 -c "import lgpio" 2>/dev/null; then
    cd /tmp
    wget -q https://github.com/joan2937/lg/archive/master.zip -O lg-master.zip
    unzip -qo lg-master.zip
    cd lg-master
    make -j"$(nproc)"
    sudo make install
    cd "$SCRIPT_DIR"
fi

# 6. Install PiSugar daemon
echo "[6/11] Installing PiSugar power manager..."
if ! systemctl is-active --quiet pisugar-server 2>/dev/null; then
    curl -sL http://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash || \
        echo "  Warning: PiSugar install failed (OK if no PiSugar hardware)"
fi

# 7. User groups
echo "[7/11] Adding user to hardware groups..."
sudo usermod -aG input,spi,gpio,i2c "$USER" 2>/dev/null || true

# 8. Waveshare e-Paper driver (vendored in lib/waveshare_epd/ — no download needed)
echo "[8/11] Verifying Waveshare e-Paper driver..."
LIB_DIR="$SCRIPT_DIR/lib/waveshare_epd"
if [ ! -f "$LIB_DIR/epd7in5_V2.py" ]; then
    echo "  ERROR: $LIB_DIR/epd7in5_V2.py not found."
    echo "  The Waveshare driver should be bundled in the project under lib/waveshare_epd/."
    echo "  Make sure you deployed the full project before running setup.sh."
    exit 1
fi

# 9. Python venv + dependencies
echo "[9/11] Creating venv and installing Python packages..."
# OPS-1: the venv is SHARED across releases (at $BASE_DIR/venv) and symlinked into
# each release tree as ./venv. This keeps releases lightweight, makes deploys fast
# (no per-release pip), and — crucially — means a rollback to an older release
# still has a working interpreter. The rendered unit references $CURRENT_LINK/venv,
# which follows: current -> releases/<ts>/venv -> $BASE_DIR/venv.
python3 -m venv "$SHARED_VENV"
"$SHARED_VENV/bin/pip" install --upgrade pip -q
"$SHARED_VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
"$SHARED_VENV/bin/pip" install evdev spidev gpiozero lgpio -q

# 10. Create directories
echo "[10/11] Creating data directories..."
mkdir -p ~/Documents/writer-deck
mkdir -p ~/.config/writer-deck

# 11. Install systemd service
echo "[11/11] Installing systemd service..."

# OPS-1: bootstrap a first release from the clone's code (only when run from a
# plain clone). Copy code into $RELEASE_DIR so the service points at an immutable
# release, never the mutable clone. We copy CONSERVATIVELY: only the app code and
# vendored driver, excluding dev files, caches, and — importantly — the shared
# venv and the releases/ dir itself (never recurse into it). rsync WITHOUT
# --delete into a fresh empty dir cannot remove anything outside $RELEASE_DIR.
if [ "$BOOTSTRAP" -eq 1 ]; then
    mkdir -p "$RELEASE_DIR"
    rsync -a \
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
        --exclude 'pyproject.toml' \
        --exclude '*.md' \
        "$SCRIPT_DIR/" "$RELEASE_DIR/"
    echo "  bootstrapped release: $RELEASE_DIR"
fi

# Symlink the release's ./venv at the shared venv (idempotent; only ever a symlink).
if [ -e "$RELEASE_DIR/venv" ] && [ ! -L "$RELEASE_DIR/venv" ]; then
    echo "  ERROR: $RELEASE_DIR/venv exists and is not a symlink; refusing to touch it."
    exit 1
fi
ln -sfn "$SHARED_VENV" "$RELEASE_DIR/venv.tmp"
mv -Tf "$RELEASE_DIR/venv.tmp" "$RELEASE_DIR/venv"

# Symlink the release's config.yaml at the persistent one in $BASE_DIR (same idea
# as venv above). config.py resolves config.yaml relative to its own file inside
# the release, so without this symlink a release can never see the user's config —
# deploy.sh deliberately excludes config.yaml from the rsync so a deploy never
# overwrites it, which only works if each release points back at the same file.
# Optional: a fresh install may not have a config.yaml yet (config_default.yaml
# alone is a valid config), so only symlink if one exists.
if [ -e "$BASE_DIR/config.yaml" ]; then
    if [ -e "$RELEASE_DIR/config.yaml" ] && [ ! -L "$RELEASE_DIR/config.yaml" ]; then
        echo "  ERROR: $RELEASE_DIR/config.yaml exists and is not a symlink; refusing to touch it."
        exit 1
    fi
    ln -sfn "$BASE_DIR/config.yaml" "$RELEASE_DIR/config.yaml.tmp"
    mv -Tf "$RELEASE_DIR/config.yaml.tmp" "$RELEASE_DIR/config.yaml"
fi

# OPS-1: point the `current` symlink at this release, so the rendered unit (which
# references $CURRENT_LINK) resolves to real code + venv. Atomic replace: build a
# temp symlink then rename over `current`. `current` is only ever a symlink here —
# never a data dir — so this is safe.
if [ -e "$CURRENT_LINK" ] && [ ! -L "$CURRENT_LINK" ]; then
    echo "  ERROR: $CURRENT_LINK exists and is not a symlink; refusing to touch it."
    echo "  Move it aside manually, then re-run setup.sh."
    exit 1
fi
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK.tmp"
mv -Tf "$CURRENT_LINK.tmp" "$CURRENT_LINK"
echo "  current -> $(readlink "$CURRENT_LINK")"

# OPS-2: render the CANONICAL checked-in template (writer-deck.service) instead of
# duplicating the unit in a here-doc. Substitute the __PLACEHOLDER__ tokens with
# the resolved paths. WorkingDirectory/ExecStart/ExecStopPost point at $CURRENT_LINK
# (the `current` symlink) so a release swap + restart switches code atomically.
UNIT_TEMPLATE="$SCRIPT_DIR/writer-deck.service"
if [ ! -f "$UNIT_TEMPLATE" ]; then
    echo "  ERROR: canonical unit template not found at $UNIT_TEMPLATE"
    exit 1
fi
sed \
    -e "s|__USER__|$USER|g" \
    -e "s|__WORKDIR__|$CURRENT_LINK|g" \
    -e "s|__VENV__|$CURRENT_LINK/venv|g" \
    "$UNIT_TEMPLATE" | sudo tee /etc/systemd/system/writer-deck.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable writer-deck.service

echo ""
echo "=== Setup complete! ==="
echo "  Reboot recommended (for SPI/I2C/BT + hardware watchdog changes)."
echo "  Then: sudo systemctl start writer-deck"
echo "  Active release: $CURRENT_LINK -> $(readlink "$CURRENT_LINK")"
echo "  Or run directly: $CURRENT_LINK/venv/bin/python $CURRENT_LINK/main.py"
echo "  Verify the hardware watchdog after reboot with: wdctl"
