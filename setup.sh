#!/usr/bin/env bash
# Writer Deck — one-shot setup script for Raspberry Pi Zero 2 W
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "=== Writer Deck Setup ==="

# 1. System packages
echo "[1/10] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-dev python3-venv python3-pip \
    libfreetype6-dev libjpeg-dev libopenjp2-7-dev \
    libgpiod-dev fonts-hack-ttf git evtest

# 2. Enable SPI + I2C, disable Bluetooth
echo "[2/10] Configuring boot options..."
BOOT_CONFIG="/boot/config.txt"
[ -f "/boot/firmware/config.txt" ] && BOOT_CONFIG="/boot/firmware/config.txt"

sudo grep -q "^dtparam=spi=on" "$BOOT_CONFIG" 2>/dev/null || \
    echo "dtparam=spi=on" | sudo tee -a "$BOOT_CONFIG" > /dev/null
sudo grep -q "^dtparam=i2c_arm=on" "$BOOT_CONFIG" 2>/dev/null || \
    echo "dtparam=i2c_arm=on" | sudo tee -a "$BOOT_CONFIG" > /dev/null
sudo grep -q "^dtoverlay=disable-bt" "$BOOT_CONFIG" 2>/dev/null || \
    echo "dtoverlay=disable-bt" | sudo tee -a "$BOOT_CONFIG" > /dev/null

# 3. Disable HDMI to save power
echo "[3/10] Disabling HDMI output..."
if ! grep -q "tvservice -o" /etc/rc.local 2>/dev/null; then
    sudo sed -i 's|^exit 0|/usr/bin/tvservice -o\nexit 0|' /etc/rc.local 2>/dev/null || true
fi

# 4. Install lgpio (required on Bookworm)
echo "[4/10] Installing lgpio..."
if ! python3 -c "import lgpio" 2>/dev/null; then
    cd /tmp
    wget -q https://github.com/joan2937/lg/archive/master.zip -O lg-master.zip
    unzip -qo lg-master.zip
    cd lg-master
    make -j"$(nproc)"
    sudo make install
    cd "$SCRIPT_DIR"
fi

# 5. Install PiSugar daemon
echo "[5/10] Installing PiSugar power manager..."
if ! systemctl is-active --quiet pisugar-server 2>/dev/null; then
    curl -sL http://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash || \
        echo "  Warning: PiSugar install failed (OK if no PiSugar hardware)"
fi

# 6. User groups
echo "[6/10] Adding user to hardware groups..."
sudo usermod -aG input,spi,gpio,i2c "$USER" 2>/dev/null || true

# 7. Waveshare e-Paper driver (vendored in lib/waveshare_epd/ — no download needed)
echo "[7/10] Verifying Waveshare e-Paper driver..."
LIB_DIR="$SCRIPT_DIR/lib/waveshare_epd"
if [ ! -f "$LIB_DIR/epd7in5_V2.py" ]; then
    echo "  ERROR: $LIB_DIR/epd7in5_V2.py not found."
    echo "  The Waveshare driver should be bundled in the project under lib/waveshare_epd/."
    echo "  Make sure you deployed the full project before running setup.sh."
    exit 1
fi

# 8. Python venv + dependencies
echo "[8/10] Creating venv and installing Python packages..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
"$VENV_DIR/bin/pip" install evdev spidev gpiozero lgpio -q

# 9. Create directories
echo "[9/10] Creating data directories..."
mkdir -p ~/Documents/writer-deck
mkdir -p ~/.config/writer-deck

# 10. Install systemd service
echo "[10/10] Installing systemd service..."
sudo tee /etc/systemd/system/writer-deck.service > /dev/null <<EOF
[Unit]
Description=Writer Deck Application
After=local-fs.target

[Service]
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$VENV_DIR/bin/python main.py
SupplementaryGroups=input spi gpio i2c
Environment="PYTHONPATH=$SCRIPT_DIR/lib"
Restart=on-failure
RestartSec=10
OOMScoreAdjust=-500
StandardOutput=journal
WatchdogSec=120
Type=simple
NotifyAccess=all

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable writer-deck.service

echo ""
echo "=== Setup complete! ==="
echo "  Reboot recommended (for SPI/I2C/BT changes)."
echo "  Then: sudo systemctl start writer-deck"
echo "  Or run directly: $VENV_DIR/bin/python main.py"
