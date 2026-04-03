import json
import sys
from pathlib import Path

ROOT = Path('/home/user/daily-market-brief/apps/api')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.strategy_registry import list_strategies
from services.live_signal_engine import scan_strategy

strategies = list_strategies()
target = None
for row in strategies:
    if str(row.get("strategy_id")) == "us_momentum_v1":
        target = row
        break

if target is None:
    raise SystemExit("us_momentum_v1 not found in strategy registry")

result = scan_strategy(target, refresh=True, include_watch=True)
print(json.dumps({
    "strategy_id": result.get("strategy_id"),
    "market": result.get("market"),
    "last_scan_at": result.get("last_scan_at"),
    "candidate_count": result.get("candidate_count"),
    "top_candidates": [
        {
            "code": item.get("code"),
            "research_status": item.get("research_status"),
            "research_unavailable": item.get("research_unavailable") ,
            "research_score": item.get("research_score"),
        }
        for item in (result.get("top_candidates") or [])[:10]
    ]
}, ensure_ascii=False, indent=2))

