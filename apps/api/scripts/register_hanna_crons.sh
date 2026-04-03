#!/usr/bin/env bash
set -euo pipefail

# Register OpenClaw cron jobs for WealthPulse Hanna research operations.
# Idempotency is handled best-effort by deleting same-name jobs first when found.

jobs=(
  "WealthPulse Hanna scanner enrich KR"
  "WealthPulse Hanna scanner enrich US"
  "WealthPulse Hanna research audit"
)

for name in "${jobs[@]}"; do
  existing_id="$(openclaw cron list 2>/dev/null | awk -F'|' -v target="$name" '
    { gsub(/^ +| +$/, "", $1); gsub(/^ +| +$/, "", $2); if ($2 == target) print $1 }
  ' | head -n1 || true)"
  if [[ -n "${existing_id}" ]]; then
    openclaw cron remove "${existing_id}" >/dev/null 2>&1 || true
  fi
done

openclaw cron add \
  --name "WealthPulse Hanna scanner enrich KR" \
  --cron "5,35 9-15 * * 1-5" \
  --tz "Asia/Seoul" \
  --session main \
  --system-event "WealthPulse Hanna scanner enrich KR run. In /home/user/daily-market-brief run: python3 apps/api/scripts/hanna_enrich_runner.py --provider openclaw --market KOSPI --limit 30 --mode missing_or_stale . If selected_count is 0, stay quiet. Only report ingest/provider issues or meaningful counts." \
  --wake now

openclaw cron add \
  --name "WealthPulse Hanna scanner enrich US" \
  --cron "5,35 9-15 * * 1-5" \
  --tz "America/New_York" \
  --session main \
  --system-event "WealthPulse Hanna scanner enrich US run. In /home/user/daily-market-brief run: python3 apps/api/scripts/hanna_enrich_runner.py --provider openclaw --market NASDAQ --limit 30 --mode missing_or_stale . If selected_count is 0, stay quiet. Only report ingest/provider issues or meaningful counts." \
  --wake now

openclaw cron add \
  --name "WealthPulse Hanna research audit" \
  --cron "20 * * * *" \
  --tz "Asia/Seoul" \
  --session main \
  --system-event "WealthPulse Hanna research audit run. In /home/user/daily-market-brief run these commands in order: python3 apps/api/scripts/research_ops.py status --provider openclaw ; python3 apps/api/scripts/research_ops.py scanner-targets --provider openclaw --market KOSPI --market NASDAQ --limit 200 ; python3 apps/api/scripts/research_ops.py enrich-targets --provider openclaw --market KOSPI --market NASDAQ --limit 200 --mode missing_or_stale . Summarize only if missing_count, stale_count, provider status, or ingest health looks concerning; otherwise stay quiet." \
  --wake now

echo "Registered Hanna cron jobs:"
openclaw cron list | grep -E 'WealthPulse Hanna'
