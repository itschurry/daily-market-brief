from __future__ import annotations

import datetime
from typing import Any

from config.company_catalog import get_company_catalog
from market_utils import normalize_market
from services.paper_runtime_store import (
    list_universe_snapshots,
    load_universe_snapshot,
    save_universe_snapshot,
)


_DEFAULT_MAX_AGE_MINUTES = 60
_BREAKOUT_SECTORS = {"반도체", "로봇", "자동차", "2차전지", "방산"}


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")


def _minutes_since(timestamp: str) -> float | None:
    try:
        parsed = datetime.datetime.fromisoformat(str(timestamp))
    except Exception:
        return None
    delta = datetime.datetime.now(datetime.timezone.utc) - parsed.astimezone(datetime.timezone.utc)
    return delta.total_seconds() / 60.0


def _normalize_entries(market: str | None = None) -> list[dict[str, Any]]:
    normalized_market = normalize_market(str(market or "").strip().upper()) if market else ""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in get_company_catalog(scope="live"):
        item_market = normalize_market(entry.market)
        if normalized_market and item_market != normalized_market:
            continue
        key = (item_market, entry.code)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "code": entry.code,
                "name": entry.name,
                "market": item_market,
                "sector": entry.sector,
            }
        )
    rows.sort(key=lambda item: (item["market"], item["sector"], item["code"]))
    return rows


def _select_universe_entries(rule_name: str, market: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_rule = str(rule_name or "top_liquidity_200").strip() or "top_liquidity_200"
    entries = _normalize_entries(market)
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    if normalized_rule == "top_liquidity_200":
        for item in entries:
            if item["market"] == "KOSPI":
                selected.append(item)
            else:
                excluded.append({**item, "reason": "market_outside_rule"})
        return selected[:200], excluded

    if normalized_rule == "us_mega_cap":
        for item in entries:
            if item["market"] == "NASDAQ":
                selected.append(item)
            else:
                excluded.append({**item, "reason": "market_outside_rule"})
        return selected[:100], excluded

    if normalized_rule == "volatility_breakout_pool":
        for item in entries:
            if item["sector"] in _BREAKOUT_SECTORS:
                selected.append(item)
            else:
                excluded.append({**item, "reason": "sector_filtered"})
        return selected[:80], excluded

    if normalized_rule == "kr_core_bluechips":
        for item in entries:
            if item["market"] == "KOSPI" and item["sector"] in {"반도체", "자동차", "금융", "플랫폼", "바이오"}:
                selected.append(item)
            else:
                excluded.append({**item, "reason": "rule_filtered"})
        return selected[:60], excluded

    for item in entries:
        selected.append(item)
    return selected[:120], excluded


def build_universe_snapshot(rule_name: str, *, market: str | None = None) -> dict[str, Any]:
    previous = load_universe_snapshot(rule_name)
    selected, excluded = _select_universe_entries(rule_name, market)
    selected_codes = [str(item.get("code") or "") for item in selected if str(item.get("code") or "")]
    previous_codes = [str(item.get("code") or "") for item in previous.get("symbols", []) if isinstance(item, dict)] if previous else []
    added = [code for code in selected_codes if code not in previous_codes]
    removed = [code for code in previous_codes if code not in selected_codes]
    snapshot = {
        "rule_name": str(rule_name or "top_liquidity_200").strip() or "top_liquidity_200",
        "market": normalize_market(str(market or "").strip().upper()) if market else (selected[0]["market"] if selected else ""),
        "created_at": str(previous.get("created_at") or _now_iso()) if previous else _now_iso(),
        "updated_at": _now_iso(),
        "symbol_count": len(selected),
        "excluded_count": len(excluded),
        "symbols": selected,
        "excluded": excluded[:50],
        "recent_changes": {
            "added": added[:20],
            "removed": removed[:20],
            "added_count": len(added),
            "removed_count": len(removed),
        },
    }
    save_universe_snapshot(snapshot["rule_name"], snapshot)
    return snapshot


def get_universe_snapshot(rule_name: str, *, market: str | None = None, refresh: bool = False, max_age_minutes: int = _DEFAULT_MAX_AGE_MINUTES) -> dict[str, Any]:
    cached = load_universe_snapshot(rule_name)
    if not refresh and cached:
        age_minutes = _minutes_since(str(cached.get("updated_at") or cached.get("created_at") or ""))
        cached_market = normalize_market(str(cached.get("market") or "").strip().upper())
        requested_market = normalize_market(str(market or "").strip().upper()) if market else ""
        if (not requested_market or cached_market == requested_market) and age_minutes is not None and age_minutes <= max_age_minutes:
            return cached
    return build_universe_snapshot(rule_name, market=market)


def list_current_universes() -> list[dict[str, Any]]:
    return list_universe_snapshots()
