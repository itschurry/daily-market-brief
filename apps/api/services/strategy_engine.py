"""Live signal book wrapper backed by strategy registry and scanner services."""

from __future__ import annotations

from typing import Any

from routes.reports import _get_market_context
from services.live_signal_engine import build_live_signal_book


def _context_snapshot() -> tuple[str, str]:
    try:
        payload = _get_market_context()
    except Exception:
        payload = {}
    context = payload.get("context") if isinstance(payload, dict) else {}
    context = context if isinstance(context, dict) else {}
    regime = str(context.get("regime") or "neutral").lower()
    risk_level = str(context.get("risk_level") or "중간")
    return regime, risk_level


def build_signal_book(
    *,
    markets: list[str] | None = None,
    cfg: dict[str, Any] | None = None,
    account: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refresh = bool((cfg or {}).get("refresh_scanner"))
    book = build_live_signal_book(markets=markets, account=account, refresh=refresh)
    regime, risk_level = _context_snapshot()
    payload = {
        **book,
        "regime": regime,
        "risk_level": risk_level,
    }
    if isinstance(payload.get("risk_guard_state"), dict):
        payload["risk_guard_state"].setdefault("regime", regime)
        payload["risk_guard_state"].setdefault("risk_level", risk_level)
    return payload


def select_entry_candidates(
    *,
    market: str,
    cfg: dict[str, Any],
    account: dict[str, Any],
    max_count: int,
) -> list[dict[str, Any]]:
    book = build_signal_book(markets=[market], cfg=cfg, account=account)
    allowed = [
        item for item in book.get("signals", [])
        if isinstance(item, dict)
        and str(item.get("market") or "").upper() == str(market or "").upper()
        and str(item.get("signal_state") or "") == "entry"
        and bool(item.get("entry_allowed"))
    ]
    return allowed[: max(0, int(max_count))]
