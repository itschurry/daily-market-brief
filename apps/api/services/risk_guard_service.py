"""Risk guard calculations for simulated/live execution gating."""

from __future__ import annotations

import datetime
import math
from collections import defaultdict
from typing import Any

from helpers import _KST
from market_utils import lookup_company_listing
from config.settings import LIVE_PERFORMANCE_STARTING_EQUITY_KRW


def _today_kst() -> str:
    return datetime.datetime.now(_KST).date().isoformat()


def _order_day(ts: str) -> str:
    try:
        return datetime.datetime.fromisoformat(ts).astimezone(_KST).date().isoformat()
    except Exception:
        return ""


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class InvalidAccountSnapshotError(ValueError):
    """Raised when risk calculations cannot trust the account snapshot."""


def validate_account_snapshot(account: Any) -> float:
    """Return a usable equity value or fail closed on an invalid snapshot."""
    if not isinstance(account, dict):
        raise InvalidAccountSnapshotError("account_snapshot_invalid")
    if account.get("ok") is False or account.get("error"):
        raise InvalidAccountSnapshotError("account_snapshot_unavailable")
    if "equity_krw" not in account or account.get("equity_krw") in (None, ""):
        raise InvalidAccountSnapshotError("account_equity_missing")

    raw_equity = account.get("equity_krw")
    if isinstance(raw_equity, bool):
        raise InvalidAccountSnapshotError("account_equity_invalid")
    try:
        equity = float(raw_equity)
    except (TypeError, ValueError) as exc:
        raise InvalidAccountSnapshotError("account_equity_invalid") from exc
    if not math.isfinite(equity) or equity <= 0.0:
        raise InvalidAccountSnapshotError("account_equity_invalid")
    return equity


def _compute_exposure(account: dict[str, Any]) -> dict[str, Any]:
    equity = validate_account_snapshot(account)
    by_market: dict[str, float] = defaultdict(float)
    by_symbol: dict[str, float] = defaultdict(float)
    by_sector: dict[str, float] = defaultdict(float)

    for position in account.get("positions", []):
        market = str(position.get("market") or "UNKNOWN").upper()
        code = str(position.get("code") or "").upper()
        value = _to_float(position.get("market_value_krw"))
        by_market[market] += value
        if code:
            by_symbol[f"{market}:{code}"] += value

            listing = lookup_company_listing(code=code, scope="core") or lookup_company_listing(code=code, scope="live")
            sector = str((listing or {}).get("sector") or position.get("sector") or "unknown")
            by_sector[sector] += value

    market_pct = {k: round(v / equity * 100.0, 4) for k, v in by_market.items()}
    symbol_pct = {k: round(v / equity * 100.0, 4) for k, v in by_symbol.items()}
    sector_pct = {k: round(v / equity * 100.0, 4) for k, v in by_sector.items()}

    return {
        "equity_krw": round(equity, 2),
        "market_pct": market_pct,
        "symbol_pct": symbol_pct,
        "sector_pct": sector_pct,
    }


def _realized_pnl_rows(account: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    mode = str(account.get("mode") or "paper").strip().lower()
    if mode in {"real", "live"}:
        if account.get("daily_realized_pnl_available") is not True:
            return False, []
        if str(account.get("daily_realized_pnl_date") or "") != _today_kst():
            return False, []
        try:
            daily_realized_pnl = float(account.get("daily_realized_pnl_krw"))
        except (TypeError, ValueError):
            return False, []
        if not math.isfinite(daily_realized_pnl):
            return False, []
        rows = account.get("daily_realized_trades")
        if not isinstance(rows, list):
            return False, []
        normalized = [dict(row) for row in rows if isinstance(row, dict)]
        if len(normalized) != len(rows):
            return False, []
        for row in normalized:
            raw_pnl = row.get("realized_pnl_krw")
            try:
                pnl = float(raw_pnl)
            except (TypeError, ValueError):
                return False, []
            if not math.isfinite(pnl):
                return False, []
        return True, normalized

    rows = account.get("orders") if isinstance(account.get("orders"), list) else []
    return True, [dict(row) for row in rows if isinstance(row, dict)]


def _realized_row_day(row: dict[str, Any]) -> str:
    explicit_date = str(row.get("date") or "").strip()
    if explicit_date:
        return explicit_date
    timestamp = str(
        row.get("filled_at")
        or row.get("ts")
        or row.get("submitted_at")
        or row.get("timestamp")
        or row.get("logged_at")
        or ""
    )
    return _order_day(timestamp)


def _daily_realized_loss(rows: list[dict[str, Any]]) -> float:
    today = _today_kst()
    loss = 0.0
    for order in rows:
        if _realized_row_day(order) != today:
            continue
        if order.get("side") and str(order.get("side") or "").lower() != "sell":
            continue
        pnl = _to_float(order.get("realized_pnl_krw"))
        if pnl < 0:
            loss += abs(pnl)
    return loss


def _consecutive_loss_count(rows: list[dict[str, Any]]) -> int:
    count = 0
    ordered_rows = sorted(
        rows,
        key=lambda row: str(
            row.get("filled_at")
            or row.get("ts")
            or row.get("submitted_at")
            or row.get("timestamp")
            or row.get("logged_at")
            or row.get("date")
            or ""
        ),
        reverse=True,
    )
    for order in ordered_rows:
        if order.get("side") and str(order.get("side") or "").lower() != "sell":
            continue
        pnl = _to_float(order.get("realized_pnl_krw"))
        if pnl < 0:
            count += 1
            continue
        break
    return count


def build_risk_guard_state(
    *,
    account: dict[str, Any],
    cfg: dict[str, Any],
    regime: str,
    risk_level: str,
) -> dict[str, Any]:
    exposure = _compute_exposure(account)
    equity = exposure["equity_krw"]

    daily_loss_limit_pct = _to_float(cfg.get("daily_loss_limit_pct"), 1.0)
    daily_loss_limit_krw = equity * max(0.1, daily_loss_limit_pct) / 100.0
    realized_pnl_available, realized_rows = _realized_pnl_rows(account)
    account_mode = str(account.get("mode") or "paper").strip().lower()
    if realized_pnl_available and account_mode in {"real", "live"}:
        consumed_loss = max(0.0, -float(account["daily_realized_pnl_krw"]))
    else:
        consumed_loss = _daily_realized_loss(realized_rows) if realized_pnl_available else 0.0
    daily_loss_left = max(0.0, daily_loss_limit_krw - consumed_loss)

    max_loss_streak = max(1, int(cfg.get("max_consecutive_loss", 3) or 3))
    cooldown_minutes = max(5, int(cfg.get("cooldown_minutes", 120) or 120))
    loss_streak = _consecutive_loss_count(realized_rows) if realized_pnl_available else 0

    cooldown_active = False
    cooldown_until = ""
    if loss_streak >= max_loss_streak:
        latest_sell_ts = ""
        for order in realized_rows:
            if not order.get("side") or str(order.get("side") or "").lower() == "sell":
                latest_sell_ts = str(
                    order.get("filled_at")
                    or order.get("ts")
                    or order.get("submitted_at")
                    or order.get("timestamp")
                    or order.get("logged_at")
                    or ""
                )
                break
        if latest_sell_ts:
            try:
                base_ts = datetime.datetime.fromisoformat(latest_sell_ts).astimezone(_KST)
                until = base_ts + datetime.timedelta(minutes=cooldown_minutes)
                cooldown_until = until.isoformat(timespec="seconds")
                cooldown_active = until > datetime.datetime.now(_KST)
            except Exception:
                cooldown_active = True
        else:
            cooldown_active = True

    reasons: list[str] = []
    entry_allowed = True

    starting_equity = _to_float(
        cfg.get("performance_starting_equity_krw"),
        _to_float(LIVE_PERFORMANCE_STARTING_EQUITY_KRW),
    )
    total_drawdown_pct = (
        max(0.0, ((starting_equity - equity) / starting_equity) * 100.0)
        if starting_equity > 0
        else 0.0
    )
    max_total_drawdown_pct = max(0.1, _to_float(cfg.get("max_total_drawdown_pct"), 3.0))

    if not realized_pnl_available:
        entry_allowed = False
        reasons.append("realized_pnl_unavailable")
    if daily_loss_left <= 0.0:
        entry_allowed = False
        reasons.append("daily_loss_limit_reached")
    if cooldown_active:
        entry_allowed = False
        reasons.append("loss_streak_cooldown")
    if starting_equity > 0 and total_drawdown_pct >= max_total_drawdown_pct:
        entry_allowed = False
        reasons.append("total_drawdown_limit_reached")

    if str(regime or "").lower() == "risk_off" and bool(cfg.get("block_buy_in_risk_off", True)):
        entry_allowed = False
        reasons.append("regime_risk_off")

    if str(risk_level or "").strip().lower() in {"높음", "high"} and bool(cfg.get("block_buy_when_risk_high", True)):
        entry_allowed = False
        reasons.append("risk_level_high")

    return {
        "entry_allowed": entry_allowed,
        "reasons": reasons,
        "daily_loss_left": round(daily_loss_left, 2),
        "daily_loss_limit": round(daily_loss_limit_krw, 2),
        "daily_realized_loss": round(consumed_loss, 2),
        "realized_pnl_available": realized_pnl_available,
        "loss_streak": loss_streak,
        "cooldown_until": cooldown_until,
        "cooldown_active": cooldown_active,
        "starting_equity_krw": round(starting_equity, 2),
        "total_drawdown_pct": round(total_drawdown_pct, 4),
        "max_total_drawdown_pct": round(max_total_drawdown_pct, 4),
        "exposure_caps": {
            "max_symbol_weight_pct": _to_float(cfg.get("max_symbol_weight_pct"), 20.0),
            "max_sector_weight_pct": _to_float(cfg.get("max_sector_weight_pct"), 35.0),
            "max_market_exposure_pct": _to_float(cfg.get("max_market_exposure_pct"), 70.0),
        },
        "exposure": exposure,
        "regime": regime,
        "risk_level": risk_level,
    }
