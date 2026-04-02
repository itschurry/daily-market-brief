from __future__ import annotations

from services.research_store import ingest_research_snapshots, load_latest_research_snapshot, load_provider_status


def handle_research_ingest_bulk(payload: dict) -> tuple[int, dict]:
    try:
        result = ingest_research_snapshots(payload if isinstance(payload, dict) else {})
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}
    status_code = 200 if result.get("accepted", 0) > 0 or result.get("rejected", 0) == 0 else 400
    return status_code, result


def handle_research_status(query: dict[str, list[str]]) -> tuple[int, dict]:
    provider = (query.get("provider") or ["openclaw"])[0] or "openclaw"
    try:
        return 200, load_provider_status(provider)
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_research_latest_snapshot(query: dict[str, list[str]]) -> tuple[int, dict]:
    symbol = ((query.get("symbol") or [""])[0] or "").strip().upper()
    market = ((query.get("market") or [""])[0] or "").strip().upper()
    provider = ((query.get("provider") or ["openclaw"])[0] or "openclaw").strip().lower()
    if not symbol or not market:
        return 400, {"ok": False, "error": "symbol_market_required"}
    try:
        snapshot = load_latest_research_snapshot(symbol, market, provider=provider)
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}
    if not snapshot:
        return 404, {"ok": False, "error": "snapshot_not_found", "symbol": symbol, "market": market, "provider": provider}
    return 200, {"ok": True, "provider": provider, "symbol": symbol, "market": market, "snapshot": snapshot}
