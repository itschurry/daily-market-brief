#!/usr/bin/env bash
set -euo pipefail

cd /home/user/wealth-pulse
.venv/bin/python apps/api/scripts/research_ops.py status
.venv/bin/python apps/api/scripts/research_ops.py scanner-targets --market KOSPI --market NASDAQ --limit 200
exec .venv/bin/python apps/api/scripts/research_ops.py enrich-targets --market KOSPI --market NASDAQ --limit 200 --mode missing_or_stale
