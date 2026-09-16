#!/usr/bin/env bash
# TwitterRadar — one-shot setup script for a fresh Ubuntu/Debian VPS.
# Run: bash scripts/setup.sh
set -e

echo "=== TwitterRadar Setup ==="

# 1. Python deps
echo "[1/5] Installing Python dependencies..."
pip3 install -r requirements.txt

# 2. twifork (optional — for keyword search)
echo "[2/5] Installing twifork (keyword search, needs login cookies)..."
pip3 install "twifork[impersonate]" 2>/dev/null && echo "  twifork installed ✓" || echo "  twifork install failed (optional — skipping)"

# 3. ProtonVPN CLI
echo "[3/5] Installing ProtonVPN CLI..."
if ! command -v protonvpn &>/dev/null; then
  sudo apt-get install -y openvpn dialog python3-pip python3-setuptools 2>/dev/null || true
  sudo pip3 install protonvpn-cli
  echo "  protonvpn-cli installed. Now run: sudo protonvpn init"
  echo "  Enter OpenVPN creds from: https://account.protonvpn.com/account"
  echo "  Then set PVPN_INIT_DONE=1 in your environment."
else
  echo "  protonvpn already installed ✓"
fi

# 4. You.com API key
echo "[4/5] You.com API key..."
if [ -z "$YDC_API_KEY" ]; then
  echo "  ⚠ YDC_API_KEY not set. Export it:"
  echo "    export YDC_API_KEY=ydc-sk-..."
else
  echo "  YDC_API_KEY set ✓"
fi

# 5. Verify
echo "[5/5] Verifying setup..."
python3 run.py status
python3 run.py test

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. (optional) sudo protonvpn init  — set up VPN rotation"
echo "  2. (optional) export TR_TWIFORK_COOKIES=cookies.json  — for keyword search"
echo "  3. python3 run.py once   — run one collection cycle"
echo "  4. python3 run.py loop   — run as a daemon"
echo "  5. Or cron:  0 */3 * * * cd /path/to/twitter-radar && python3 run.py once"
