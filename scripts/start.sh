#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
[[ -f /etc/neurosis-tunnel/config.yml ]] || { echo 'Existing tunnel configuration is missing at /etc/neurosis-tunnel/config.yml.' >&2; exit 1; }
# Prove origin isolation before enabling Internet ingress.
python3 scripts/verify_isolation.py --origin-only
runuser -u neurosis-tunnel -- /usr/local/bin/cloudflared --config /etc/neurosis-tunnel/config.yml tunnel ingress validate
install -m 0644 deploy/neurosis-cloudflared.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now neurosis-cloudflared.service
python3 scripts/verify_isolation.py
