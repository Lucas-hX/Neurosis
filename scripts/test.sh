#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID != 0 ]] || { echo 'Run tests as a regular user; initdb refuses root.' >&2; exit 1; }
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pytest -q
