from __future__ import annotations

from services.execution_service import get_execution_service
from services.live_signal_engine import scan_live_strategies


def handle_scanner_status(query: dict[str, list[str]]) -> tuple[int, dict]:
    try:
        refresh = (query.get("refresh", ["0"])[0] or "0").strip() == "1"
        markets = [str(item or "").strip().upper() for item in query.get("market", []) if str(item or "").strip()]
        _, execution_payload = get_execution_service().paper_engine_status()
        account = execution_payload.get("account") if isinstance(execution_payload, dict) else {}
        rows = scan_live_strategies(markets=markets or None, account=account if isinstance(account, dict) else {}, refresh=refresh)
        return 200, {"ok": True, "items": rows, "count": len(rows)}
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}
