"""백테스트/최적화용 유니버스 동적 조회."""

from __future__ import annotations

from typing import TypedDict

from loguru import logger
from market_utils import normalize_market


class BacktestUniverseEntry(TypedDict):
    name: str
    code: str
    market: str


def _load_snapshot_universe(rule_name: str, *, market_filter: str) -> list[BacktestUniverseEntry]:
    try:
        from services.universe_builder import get_universe_snapshot
    except Exception:
        logger.exception("universe_builder import failed")
        return []

    payload = get_universe_snapshot(rule_name, market=market_filter, refresh=False)
    symbols = payload.get("symbols") if isinstance(payload.get("symbols"), list) else []
    target_market = normalize_market(market_filter).upper()
    rows: list[BacktestUniverseEntry] = []
    seen: set[str] = set()

    for row in symbols:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip().upper()
        market = normalize_market(str(row.get("market") or target_market or ""))
        name = str(row.get("name") or code).strip()
        if not code or code in seen:
            continue
        if target_market and market and market != target_market:
            continue
        seen.add(code)
        rows.append({
            "name": name or code,
            "code": code,
            "market": market or target_market or "KOSPI",
        })
    return rows


def get_sp100_nasdaq_universe() -> list[BacktestUniverseEntry]:
    return [entry for entry in get_sp100_universe() if normalize_market(entry["market"]) == "NASDAQ"]


def get_sp100_universe() -> list[BacktestUniverseEntry]:
    return _load_snapshot_universe("sp500", market_filter="")


def get_kospi100_universe() -> list[BacktestUniverseEntry]:
    return _load_snapshot_universe("kospi", market_filter="KOSPI")


def get_kospi50_universe() -> list[BacktestUniverseEntry]:
    return get_kospi100_universe()


def get_sp50_universe() -> list[BacktestUniverseEntry]:
    return get_sp100_universe()


def get_kospi_universe() -> list[BacktestUniverseEntry]:
    return get_kospi100_universe()
