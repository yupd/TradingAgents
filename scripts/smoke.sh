#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/pytest -q
echo
echo "Offline suite passed. Manual integration checks (need a configured model):"
echo "  .venv/bin/python -m cli.main brief --date $(date +%F)"
echo "  .venv/bin/python -m cli.main deep 600519"
echo "  .venv/bin/python -m cli.main deep 0700.HK"
