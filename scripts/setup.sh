#!/bin/bash
# PyFarm setup script for Raspberry Pi (run as root)
set -e

[[ $EUID -ne 0 ]] && { echo "Run as root (sudo)"; exit 1; }

echo "Creating pyfarm user..."
id -u pyfarm &>/dev/null || useradd -m -s /bin/bash pyfarm
usermod -aG gpio pyfarm 2>/dev/null || true

echo "Installing system dependencies..."
apt-get update -q
apt-get install -y -q python3-pip python3-dev build-essential

echo "Creating data directory..."
mkdir -p /var/lib/pyfarm /etc/pyfarm
chown pyfarm:pyfarm /var/lib/pyfarm /etc/pyfarm

echo "Installing systemd service..."
cp "$(dirname "$0")/../pyfarm-control.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable pyfarm-control

echo ""
echo "Done. Next steps:"
echo "  1. Copy your GrowSpec to /etc/pyfarm/grow.yaml"
echo "  2. Install pyfarm:  pip3 install -e /path/to/pyfarm-control"
echo "  3. Start:           systemctl start pyfarm-control"
echo "  4. Logs:            journalctl -u pyfarm-control -f"
echo ""
echo "Optional sensor libraries:"
echo "  pip3 install adafruit-circuitpython-dht   # DHT22"
echo "  pip3 install adafruit-circuitpython-mcp3xxx adafruit-circuitpython-busdevice  # ADC"
