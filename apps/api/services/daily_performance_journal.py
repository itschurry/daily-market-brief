from __future__ import annotations

import datetime
import json
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from config.market_calendar import is_market_trading_day
from config.settings import RUNTIME_DIR
from market_utils import lookup_company_listing
from services.json_utils import json_dump_text
from services.runtime_store import load_engine_state


KST = ZoneInfo("Asia/Seoul")
JOURNAL_DIR = RUNTIME_DIR / "daily_performance"
ENGINE_CYCLES_DIR = RUNTIME_DIR / "engine_cycles"
JOURNAL_TIME_KST = datetime.time(hour=15, minute=40, tzinfo=KST)
_scheduler_stop = threading.Event()
_scheduler_thread: threading.Thread | None = None


def _validate_date_key(date_key: str) -> str:
    parsed = datetime.date.fromisoformat(str(date_key or ""))
    normalized = parsed.isoformat()
    if normalized != date_key:
        raise ValueError(f"잘못된 날짜 형식: {date_key}")
    return normalized


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 객체가 아님: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dump_text(payload, indent=2), encoding="utf-8")


def _read_cycles(date_key: str) -> list[dict[str, Any]]:
    path = ENGINE_CYCLES_DIR / f"{date_key}.jsonl"
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    cutoff = datetime.datetime.combine(
        datetime.date.fromisoformat(date_key),
        JOURNAL_TIME_KST,
    )
    rows = [
        row for row in rows
        if (row.get("started_at") or row.get("logged_at"))
        and _kst_date(row.get("started_at") or row.get("logged_at")) == date_key
        and datetime.datetime.fromisoformat(
            str(row.get("started_at") or row.get("logged_at")).replace("Z", "+00:00")
        ).astimezone(KST) <= cutoff
    ]
    if not rows:
        raise ValueError(f"엔진 사이클이 없음: {date_key}")
    return rows


def _kst_date(value: Any) -> str:
    parsed = datetime.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(KST).date().isoformat()


def _kst_iso(value: Any) -> str:
    parsed = datetime.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(KST).isoformat(timespec="seconds")


def _order_state(order: dict[str, Any]) -> str:
    for key in ("lifecycle_state", "execution_status", "status"):
        value = str(order.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _order_timestamp(order: dict[str, Any]) -> Any:
    return (
        order.get("filled_at")
        or order.get("ts")
        or order.get("timestamp")
        or order.get("submitted_at")
        or order.get("logged_at")
    )


def _order_identity(order: dict[str, Any]) -> str:
    explicit = str(order.get("order_id") or order.get("broker_order_id") or order.get("trace_id") or "").strip()
    if explicit:
        return explicit
    return ":".join([
        str(order.get("market") or "").strip().upper(),
        str(order.get("code") or "").strip().upper(),
        str(order.get("side") or "").strip().lower(),
        str(_order_timestamp(order) or "").strip(),
        str(int(_safe_float(order.get("quantity")))),
    ])


def _merge_filled_orders(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def _account_orders(account: dict[str, Any]) -> list[dict[str, Any]]:
    orders = account.get("orders") if isinstance(account.get("orders"), list) else []
    deduplicated: dict[str, dict[str, Any]] = {}
    for order in orders:
        if not isinstance(order, dict) or _order_state(order) not in {"filled", "partial_fill"}:
            continue
        item = dict(order)
        key = _order_identity(item)
        deduplicated[key] = _merge_filled_orders(deduplicated.get(key, {}), item)
    return sorted(deduplicated.values(), key=lambda item: str(_order_timestamp(item) or ""))


def _daily_orders(cycles: list[dict[str, Any]], date_key: str) -> list[dict[str, Any]]:
    account = cycles[-1].get("account") if isinstance(cycles[-1].get("account"), dict) else {}
    orders = _account_orders(account)
    result = []
    for order in orders:
        timestamp = _order_timestamp(order)
        if timestamp and _kst_date(timestamp) == date_key:
            result.append(dict(order))
    return result


def _entry_metadata(cycles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cycle in cycles:
        buys = cycle.get("executed_buys") if isinstance(cycle.get("executed_buys"), list) else []
        for buy in buys:
            if not isinstance(buy, dict):
                continue
            code = str(buy.get("code") or "").strip()
            if code:
                result[code] = dict(buy)
    return result


def _exit_metadata(cycles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cycle in cycles:
        sells = cycle.get("executed_sells") if isinstance(cycle.get("executed_sells"), list) else []
        for sell in sells:
            if not isinstance(sell, dict):
                continue
            code = str(sell.get("code") or "").strip()
            if code:
                result[code] = dict(sell)
    return result


def _aggregate_broker_profits(trades: list[dict[str, Any]], date_key: str) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for trade in trades:
        if not isinstance(trade, dict) or str(trade.get("date") or "") != date_key:
            raise ValueError(f"KIS 실현손익 거래일 불일치: {date_key}")
        code = str(trade.get("code") or "").strip()
        quantity = int(_safe_float(trade.get("quantity")))
        if not code or quantity <= 0:
            raise ValueError("KIS 실현손익 종목 또는 수량 누락")
        current = aggregated.setdefault(code, {
            "code": code,
            "name": trade.get("name"),
            "market": trade.get("market") or "KOSPI",
            "quantity": 0,
            "entry_notional_krw": 0.0,
            "exit_notional_krw": 0.0,
            "buy_quantity": 0,
            "buy_notional_krw": 0.0,
            "realized_pnl_krw": 0.0,
            "total_cost_krw": 0.0,
        })
        current["quantity"] += quantity
        current["entry_notional_krw"] += _safe_float(trade.get("entry_price_krw")) * quantity
        current["exit_notional_krw"] += _safe_float(trade.get("sell_notional_krw")) or _safe_float(trade.get("exit_price_krw")) * quantity
        current["buy_quantity"] += int(_safe_float(trade.get("buy_quantity")))
        current["buy_notional_krw"] += _safe_float(trade.get("buy_notional_krw"))
        current["realized_pnl_krw"] += _safe_float(trade.get("realized_pnl_krw"))
        current["total_cost_krw"] += _safe_float(trade.get("total_cost_krw"))
    for item in aggregated.values():
        quantity = int(item["quantity"])
        item["entry_price_krw"] = item["entry_notional_krw"] / quantity
        item["exit_price_krw"] = item["exit_notional_krw"] / quantity
        item["return_pct"] = item["realized_pnl_krw"] / item["entry_notional_krw"] * 100 if item["entry_notional_krw"] > 0 else None
    return aggregated


def _live_broker_orders(
    broker_activity: dict[str, Any],
    date_key: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    fills_payload = broker_activity.get("fills") if isinstance(broker_activity.get("fills"), dict) else {}
    profits_payload = broker_activity.get("profits") if isinstance(broker_activity.get("profits"), dict) else {}
    fills = _account_orders({"orders": fills_payload.get("orders") or []})
    for order in fills:
        timestamp = _order_timestamp(order)
        if not timestamp or _kst_date(timestamp) != date_key:
            raise ValueError(f"KIS 체결 거래일 불일치: {date_key}")

    summary = fills_payload.get("summary") if isinstance(fills_payload.get("summary"), dict) else {}
    if "fees_and_tax_krw" not in summary:
        raise ValueError("KIS 일별 체결 비용 합계 누락")
    fees_krw = _safe_float(summary.get("fees_and_tax_krw"))
    profits = _aggregate_broker_profits(
        profits_payload.get("trades") if isinstance(profits_payload.get("trades"), list) else [],
        date_key,
    )
    sell_fills_by_code: dict[str, list[dict[str, Any]]] = {}
    buy_orders: list[dict[str, Any]] = []
    for order in fills:
        side = str(order.get("side") or "").lower()
        code = str(order.get("code") or "").strip()
        if side == "buy":
            buy_orders.append(dict(order))
        elif side == "sell":
            sell_fills_by_code.setdefault(code, []).append(dict(order))

    if set(sell_fills_by_code) != set(profits):
        raise ValueError("KIS 체결 매도와 실현손익 종목이 일치하지 않음")
    sell_orders: list[dict[str, Any]] = []
    for code, profit in profits.items():
        matched_fills = sell_fills_by_code[code]
        filled_quantity = sum(int(_safe_float(order.get("quantity"))) for order in matched_fills)
        if filled_quantity != int(profit["quantity"]):
            raise ValueError(f"KIS 체결 매도수량과 실현손익 수량 불일치: {code}")
        last_fill = max(matched_fills, key=lambda item: str(_order_timestamp(item) or ""))
        sell_orders.append({
            **last_fill,
            "quantity": int(profit["quantity"]),
            "filled_quantity": int(profit["quantity"]),
            "filled_price_local": profit["exit_price_krw"],
            "filled_price_krw": profit["exit_price_krw"],
            "notional_local": profit["exit_notional_krw"],
            "notional_krw": profit["exit_notional_krw"],
            "realized_pnl_krw": profit["realized_pnl_krw"],
            "fee_krw": profit["total_cost_krw"],
            "return_pct": profit["return_pct"],
            "realized_pnl_includes_all_costs": True,
            "broker_source": "kis_inquire_period_trade_profit",
        })
    return fills, sorted([*buy_orders, *sell_orders], key=lambda item: str(_order_timestamp(item) or "")), fees_krw


def _prior_open_position_metadata(date_key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(JOURNAL_DIR.glob("*.json")):
        journal = _read_json(path)
        if str(journal.get("date") or "") >= date_key:
            continue
        trading = journal.get("trading") if isinstance(journal.get("trading"), dict) else {}
        positions = trading.get("open_at_close") if isinstance(trading.get("open_at_close"), list) else []
        for position in positions:
            if isinstance(position, dict) and position.get("code"):
                result[str(position["code"])] = dict(position)
    return result


def _previous_journal(date_key: str) -> dict[str, Any]:
    paths = [path for path in sorted(JOURNAL_DIR.glob("*.json")) if path.stem < date_key]
    return _read_json(paths[-1]) if paths else {}


def _company_name(code: str, market: str, *values: Any) -> str:
    for value in values:
        name = str(value or "").strip()
        if name and name != code:
            return name
    listing = lookup_company_listing(code=code, market=market, scope="live")
    return str((listing or {}).get("name") or code)


def _build_closed_trades(
    orders: list[dict[str, Any]],
    date_key: str,
    entry_meta: dict[str, dict[str, Any]],
    exit_meta: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    exit_meta = exit_meta or {}
    buys_by_code: dict[str, list[dict[str, Any]]] = {}
    same_day: list[dict[str, Any]] = []
    carry_in: list[dict[str, Any]] = []
    for order in orders:
        code = str(order.get("code") or "").strip()
        side = str(order.get("side") or "").lower()
        if side == "buy":
            buy_lot = dict(order)
            buy_lot["_remaining_quantity"] = int(_safe_float(order.get("quantity")))
            buys_by_code.setdefault(code, []).append(buy_lot)
            continue
        if side != "sell":
            continue
        if not buys_by_code.get(code):
            prior = entry_meta.get(code, {})
            prior_quantity = int(_safe_float(prior.get("quantity")))
            prior_entry_at = prior.get("entry_at")
            prior_entry_price = prior.get("entry_price_krw")
            if prior_quantity > 0 and prior_entry_at and prior_entry_price not in (None, ""):
                buys_by_code[code] = [{
                    "code": code,
                    "name": prior.get("name"),
                    "market": prior.get("market") or order.get("market"),
                    "quantity": prior_quantity,
                    "filled_price_krw": prior_entry_price,
                    "fee_krw": prior.get("entry_fee_krw") or 0.0,
                    "ts": prior_entry_at,
                    "filled_at": prior_entry_at,
                    "_remaining_quantity": prior_quantity,
                }]
        if not buys_by_code.get(code):
            continue
        remaining_to_sell = int(_safe_float(order.get("quantity")))
        matched_lots: list[tuple[dict[str, Any], int]] = []
        while remaining_to_sell > 0 and buys_by_code.get(code):
            buy_lot = buys_by_code[code][0]
            available = int(_safe_float(buy_lot.get("_remaining_quantity")))
            matched_quantity = min(available, remaining_to_sell)
            matched_lots.append((buy_lot, matched_quantity))
            buy_lot["_remaining_quantity"] = available - matched_quantity
            remaining_to_sell -= matched_quantity
            if buy_lot["_remaining_quantity"] <= 0:
                buys_by_code[code].pop(0)
        if not matched_lots:
            continue
        buy = matched_lots[0][0]
        meta = entry_meta.get(code, {})
        quantity = sum(matched_quantity for _, matched_quantity in matched_lots)
        entry_notional = sum(_safe_float(lot.get("filled_price_krw")) * matched_quantity for lot, matched_quantity in matched_lots)
        entry_price = entry_notional / quantity if quantity > 0 else 0.0
        entry_fee = sum(
            _safe_float(lot.get("fee_krw")) * matched_quantity / max(1, int(_safe_float(lot.get("quantity"))))
            for lot, matched_quantity in matched_lots
        )
        exit_price = _safe_float(order.get("filled_price_krw"))
        realized_pnl = _safe_float(order.get("realized_pnl_krw"))
        entry_ts = _order_timestamp(buy)
        exit_ts = _order_timestamp(order)
        held_seconds = int(
            (
                datetime.datetime.fromisoformat(str(exit_ts).replace("Z", "+00:00"))
                - datetime.datetime.fromisoformat(str(entry_ts).replace("Z", "+00:00"))
            ).total_seconds()
        )
        trade = {
            "code": code,
            "name": _company_name(code, str(order.get("market") or buy.get("market") or ""), meta.get("name"), buy.get("name"), order.get("name")),
            "market": str(order.get("market") or buy.get("market") or ""),
            "quantity": quantity,
            "entry_at": _kst_iso(entry_ts),
            "exit_at": _kst_iso(exit_ts),
            "holding_seconds": held_seconds,
            "entry_price_krw": round(entry_price, 4),
            "exit_price_krw": round(exit_price, 4),
            "entry_notional_krw": round(entry_notional, 2),
            "entry_fee_krw": round(entry_fee, 2),
            "exit_fee_krw": round(_safe_float(order.get("fee_krw")), 2),
            "realized_pnl_krw": round(realized_pnl, 2),
            "return_pct": round(_safe_float(order.get("return_pct")), 4) if order.get("return_pct") not in (None, "") else (round(realized_pnl / entry_notional * 100, 4) if entry_notional > 0 else None),
            "exit_reason": str(order.get("note") or exit_meta.get(code, {}).get("reason") or ""),
            "strategy_type": str(meta.get("strategy_type") or ""),
            "expected_value": meta.get("expected_value"),
            "realized_pnl_includes_all_costs": bool(order.get("realized_pnl_includes_all_costs")),
            "broker_source": order.get("broker_source"),
            "entry_plan": {
                "entry_plan_price": buy.get("entry_plan_price"),
                "stop_loss_price": buy.get("stop_loss_price"),
                "take_profit_price": buy.get("take_profit_price"),
                "stop_loss_pct": buy.get("stop_loss_pct"),
                "take_profit_pct": buy.get("take_profit_pct"),
            },
        }
        if _kst_date(exit_ts) != date_key:
            continue
        if _kst_date(entry_ts) == date_key:
            same_day.append(trade)
        else:
            carry_in.append(trade)
    return same_day, carry_in, buys_by_code


def _build_open_at_close(
    account: dict[str, Any],
    unmatched_buys: dict[str, list[dict[str, Any]]],
    date_key: str,
    entry_meta: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    positions = account.get("positions") if isinstance(account.get("positions"), list) else []
    for position in positions:
        if not isinstance(position, dict):
            continue
        code = str(position.get("code") or "").strip()
        buy_lots = unmatched_buys.get(code) or [{}]
        buy = buy_lots[-1]
        entry_ts = position.get("entry_ts") or buy.get("ts") or buy.get("logged_at")
        if not code or not entry_ts:
            continue
        quantity = int(_safe_float(position.get("quantity")))
        entry_price = _safe_float(position.get("avg_price_krw") or buy.get("filled_price_krw"))
        close_price = _safe_float(position.get("last_price_krw"))
        unrealized = _safe_float(position.get("unrealized_pnl_krw"))
        meta = entry_meta.get(code, {})
        result.append({
            "code": code,
            "name": _company_name(code, str(position.get("market") or ""), meta.get("name"), position.get("name"), buy.get("name")),
            "market": str(position.get("market") or buy.get("market") or ""),
            "quantity": quantity,
            "entry_at": _kst_iso(entry_ts),
            "position_origin": "opened_today" if _kst_date(entry_ts) == date_key else "carried_in",
            "entry_price_krw": round(entry_price, 4),
            "close_price_krw": round(close_price, 4),
            "market_value_krw": round(_safe_float(position.get("market_value_krw")) or close_price * quantity, 2),
            "entry_fee_krw": round(sum(
                _safe_float(lot.get("fee_krw"))
                * int(_safe_float(lot.get("_remaining_quantity") or lot.get("quantity")))
                / max(1, int(_safe_float(lot.get("quantity"))))
                for lot in buy_lots
            ), 2),
            "unrealized_pnl_krw": round(unrealized, 2),
            "return_pct": round(_safe_float(position.get("unrealized_pnl_pct")), 4),
        })
    return result


def _latest_account_orders(mode: str) -> list[dict[str, Any]]:
    filename = "simulated_account_state.json" if mode == "paper" else "live_account_state.json"
    path = RUNTIME_DIR / "accounts" / filename
    return _account_orders(_read_json(path)) if path.exists() else []


def _stored_closed_trades() -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    for path in sorted(JOURNAL_DIR.glob("*.json")):
        journal = _read_json(path)
        trading = journal.get("trading") if isinstance(journal.get("trading"), dict) else {}
        rows = trading.get("trades") if isinstance(trading.get("trades"), list) else []
        trades.extend(dict(row) for row in rows if isinstance(row, dict) and row.get("exit_at"))
    return sorted(trades, key=lambda item: str(item.get("exit_at") or ""))


def _build_follow_up(
    open_positions: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    date_key: str,
    closed_trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    closed_trades = closed_trades or []
    outcomes: list[dict[str, Any]] = []
    for position in open_positions:
        code = str(position.get("code") or "")
        exact_trade = next((
            trade for trade in closed_trades
            if str(trade.get("code") or "") == code
            and trade.get("exit_at")
            and _kst_date(trade.get("exit_at")) > date_key
        ), None)
        exit_order = next((
            order for order in orders
            if str(order.get("code") or "") == code
            and str(order.get("side") or "").lower() == "sell"
            and _order_timestamp(order)
            and _kst_date(_order_timestamp(order)) > date_key
            and order.get("filled_price_krw") not in (None, "")
            and order.get("realized_pnl_krw") not in (None, "")
        ), None)
        outcome = {
            "code": code,
            "name": position.get("name"),
            "entry_at": position.get("entry_at"),
            "close_date": date_key,
            "status": "closed" if exact_trade or exit_order else "open",
        }
        if exact_trade:
            outcome.update({
                "exit_at": exact_trade.get("exit_at"),
                "exit_price_krw": exact_trade.get("exit_price_krw"),
                "realized_pnl_krw": exact_trade.get("realized_pnl_krw"),
                "return_pct": exact_trade.get("return_pct"),
                "exit_reason": str(exact_trade.get("exit_reason") or ""),
            })
        elif exit_order:
            entry_notional = _safe_float(position.get("entry_price_krw")) * int(_safe_float(position.get("quantity")))
            realized = _safe_float(exit_order.get("realized_pnl_krw"))
            outcome.update({
                "exit_at": _kst_iso(_order_timestamp(exit_order)),
                "exit_price_krw": round(_safe_float(exit_order.get("filled_price_krw")), 4),
                "realized_pnl_krw": round(realized, 2),
                "return_pct": round(realized / entry_notional * 100, 4) if entry_notional > 0 else None,
                "exit_reason": str(exit_order.get("note") or ""),
            })
        outcomes.append(outcome)
    return {"as_of": datetime.datetime.now(KST).isoformat(timespec="seconds"), "outcomes": outcomes}


def _market_snapshot(date_key: str, market_payload: dict[str, Any]) -> dict[str, Any]:
    history = market_payload.get("kospi_history") if isinstance(market_payload.get("kospi_history"), list) else []
    point = next((item for item in history if isinstance(item, dict) and item.get("date") == date_key), None)
    if point is None:
        raise ValueError(f"KOSPI 종가 데이터가 없음: {date_key}")
    return {
        "kospi_close": point.get("close"),
        "kospi_return_pct": point.get("pct"),
        "source": "naver_index_history",
    }


def build_daily_performance_journal(
    date_key: str,
    *,
    market_payload: dict[str, Any],
    broker_activity: dict[str, Any] | None = None,
    broker_activity_loader: Callable[[str], dict[str, Any]] | None = None,
    generated_at: datetime.datetime | None = None,
) -> dict[str, Any]:
    date_key = _validate_date_key(date_key)
    cycles = _read_cycles(date_key)
    first_account = cycles[0].get("account") if isinstance(cycles[0].get("account"), dict) else {}
    last_account = cycles[-1].get("account") if isinstance(cycles[-1].get("account"), dict) else {}
    if not first_account or not last_account:
        raise ValueError(f"계좌 스냅샷이 없는 엔진 사이클: {date_key}")

    mode = str(last_account.get("mode") or "unknown").strip().lower()
    live_mode = mode in {"live", "real"}
    if live_mode:
        if broker_activity is None:
            if broker_activity_loader is None:
                raise ValueError("실거래 일별 저널에는 KIS 체결·손익 원장이 필요함")
            broker_activity = broker_activity_loader(date_key)
        if not isinstance(broker_activity, dict):
            raise ValueError("KIS 체결·손익 원장 형식 오류")
        orders, all_orders, daily_fees_krw = _live_broker_orders(broker_activity, date_key)
    else:
        orders = _daily_orders(cycles, date_key)
        all_orders = _account_orders(last_account)
        daily_fees_krw = sum(_safe_float(order.get("fee_krw")) for order in orders)
    previous_journal = _previous_journal(date_key)
    entry_meta = _prior_open_position_metadata(date_key)
    entry_meta.update(_entry_metadata(cycles))
    same_day_trades, carry_in_exits, unmatched_buys = _build_closed_trades(
        all_orders,
        date_key,
        entry_meta,
        _exit_metadata(cycles),
    )
    open_at_close = _build_open_at_close(last_account, unmatched_buys, date_key, entry_meta)
    closed_trades = same_day_trades + carry_in_exits
    previous_account = previous_journal.get("account") if isinstance(previous_journal.get("account"), dict) else {}
    starting_equity = _safe_float(previous_account.get("ending_equity_krw") or first_account.get("equity_krw"))
    ending_equity = _safe_float(last_account.get("equity_krw"))
    net_pnl = ending_equity - starting_equity
    market = _market_snapshot(date_key, market_payload)
    daily_return = net_pnl / starting_equity * 100 if starting_equity > 0 else 0.0
    wins = [trade for trade in closed_trades if _safe_float(trade.get("realized_pnl_krw")) > 0]
    losses = [trade for trade in closed_trades if _safe_float(trade.get("realized_pnl_krw")) < 0]
    gross_profit = sum(_safe_float(trade.get("realized_pnl_krw")) for trade in wins)
    gross_loss = abs(sum(_safe_float(trade.get("realized_pnl_krw")) for trade in losses))
    skip_reasons: Counter[str] = Counter()
    blocked_reasons: Counter[str] = Counter()
    rotation_attempts = 0
    rotation_executions = 0
    for cycle in cycles:
        skip_reasons.update({str(key): int(value) for key, value in (cycle.get("skip_reason_counts") or {}).items()})
        blocked_reasons.update({str(key): int(value) for key, value in (cycle.get("blocked_reason_counts") or {}).items()})
        rotation = cycle.get("rotation_summary") if isinstance(cycle.get("rotation_summary"), dict) else {}
        rotation_attempts += int(rotation.get("attempted_count") or 0)
        rotation_executions += int(rotation.get("executed_count") or 0)

    initial_equity = _safe_float(last_account.get("starting_equity_krw") or last_account.get("initial_cash_krw"))
    now = (generated_at or datetime.datetime.now(KST)).astimezone(KST)
    start_positions = {
        str(position.get("code") or ""): position
        for position in (first_account.get("positions") or [])
        if isinstance(position, dict)
    }
    previous_trading = previous_journal.get("trading") if isinstance(previous_journal.get("trading"), dict) else {}
    previous_open_positions = previous_trading.get("open_at_close") if isinstance(previous_trading.get("open_at_close"), list) else []
    for position in previous_open_positions:
        if not isinstance(position, dict) or not position.get("code"):
            continue
        start_positions[str(position["code"])] = {
            **position,
            "last_price_krw": position.get("close_price_krw"),
        }
    same_day_contribution = sum(
        _safe_float(trade.get("realized_pnl_krw"))
        - (0.0 if trade.get("realized_pnl_includes_all_costs") else _safe_float(trade.get("entry_fee_krw")))
        for trade in same_day_trades
    )
    carry_in_contribution = 0.0
    for trade in carry_in_exits:
        start_position = start_positions.get(str(trade.get("code") or ""), {})
        quantity = int(_safe_float(trade.get("quantity")))
        start_value = _safe_float(start_position.get("last_price_krw")) * quantity
        exit_value = _safe_float(trade.get("exit_price_krw")) * quantity - _safe_float(trade.get("exit_fee_krw"))
        carry_in_contribution += exit_value - start_value
    open_contribution = 0.0
    for position in open_at_close:
        if position.get("position_origin") == "opened_today":
            open_contribution += _safe_float(position.get("unrealized_pnl_krw")) - _safe_float(position.get("entry_fee_krw"))
        else:
            start_position = start_positions.get(str(position.get("code") or ""), {})
            open_contribution += _safe_float(position.get("market_value_krw")) - _safe_float(start_position.get("market_value_krw"))
    attributed = same_day_contribution + carry_in_contribution + open_contribution
    latest_orders = _latest_account_orders(str(last_account.get("mode") or "unknown"))
    payload = {
        "schema_version": 2,
        "date": date_key,
        "generated_at": now.isoformat(timespec="seconds"),
        "mode": mode,
        "account": {
            "starting_equity_krw": round(starting_equity, 2),
            "ending_equity_krw": round(ending_equity, 2),
            "ending_cash_krw": round(_safe_float(last_account.get("cash_krw")), 2),
            "ending_market_value_krw": round(_safe_float(last_account.get("market_value_krw")), 2),
            "net_pnl_krw": round(net_pnl, 2),
            "daily_return_pct": round(daily_return, 4),
            "cumulative_return_pct": round((ending_equity - initial_equity) / initial_equity * 100, 4) if initial_equity > 0 else None,
            "fees_krw": round(daily_fees_krw, 2),
            "open_position_count": len(last_account.get("positions") or []),
        },
        "market": {
            **market,
            "excess_return_pct_points": round(daily_return - _safe_float(market.get("kospi_return_pct")), 4),
        },
        "trading": {
            "buy_count": sum(1 for order in orders if str(order.get("side") or "").lower() == "buy"),
            "sell_count": sum(1 for order in orders if str(order.get("side") or "").lower() == "sell"),
            "round_trip_count": len(same_day_trades),
            "closed_trade_count": len(closed_trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate_pct": round(len(wins) / len(closed_trades) * 100, 2) if closed_trades else None,
            "gross_profit_krw": round(gross_profit, 2),
            "gross_loss_krw": round(gross_loss, 2),
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
            "average_holding_seconds": round(sum(int(trade["holding_seconds"]) for trade in closed_trades) / len(closed_trades), 2) if closed_trades else None,
            "trades": closed_trades,
            "same_day_round_trips": same_day_trades,
            "carry_in_exits": carry_in_exits,
            "open_at_close": open_at_close,
        },
        "pnl_attribution": {
            "same_day_closed_contribution_krw": round(same_day_contribution, 2),
            "carry_in_exit_contribution_krw": round(carry_in_contribution, 2),
            "open_position_contribution_krw": round(open_contribution, 2),
            "unattributed_krw": round(net_pnl - attributed, 2),
            "realized_exit_pnl_krw": round(sum(_safe_float(trade.get("realized_pnl_krw")) for trade in closed_trades), 2),
            "open_unrealized_pnl_krw": round(sum(_safe_float(position.get("unrealized_pnl_krw")) for position in open_at_close), 2),
            "net_pnl_krw": round(net_pnl, 2),
        },
        "follow_up": _build_follow_up(open_at_close, latest_orders, date_key, _stored_closed_trades()),
        "diagnostics": {
            "engine_cycle_count": len(cycles),
            "skip_reason_counts": dict(skip_reasons),
            "blocked_reason_counts": dict(blocked_reasons),
            "rotation_attempted_count": rotation_attempts,
            "rotation_executed_count": rotation_executions,
            "trade_ledger_source": "kis" if live_mode else "simulated_account",
        },
        "strategy_config": load_engine_state(default={}).get("current_config") or {},
    }
    return payload


def generate_daily_performance_journal(
    date_key: str,
    *,
    market_loader: Callable[[], dict[str, Any]],
    broker_activity_loader: Callable[[str], dict[str, Any]] | None = None,
    generated_at: datetime.datetime | None = None,
) -> dict[str, Any]:
    date_key = _validate_date_key(date_key)
    payload = build_daily_performance_journal(
        date_key,
        market_payload=market_loader(),
        broker_activity_loader=broker_activity_loader,
        generated_at=generated_at,
    )
    _write_json(JOURNAL_DIR / f"{date_key}.json", payload)
    _reconcile_stored_follow_ups(str(payload.get("mode") or "unknown"))
    return payload


def _reconcile_stored_follow_ups(mode: str) -> None:
    orders = _latest_account_orders(mode)
    closed_trades = _stored_closed_trades()
    for path in JOURNAL_DIR.glob("*.json"):
        journal = _read_json(path)
        trading = journal.get("trading") if isinstance(journal.get("trading"), dict) else {}
        open_positions = trading.get("open_at_close") if isinstance(trading.get("open_at_close"), list) else []
        if int(journal.get("schema_version") or 0) < 2 or not open_positions:
            continue
        journal["follow_up"] = _build_follow_up(
            open_positions,
            orders,
            str(journal.get("date") or ""),
            closed_trades,
        )
        _write_json(path, journal)


def read_daily_performance_journal(date_key: str) -> dict[str, Any]:
    date_key = _validate_date_key(date_key)
    return _read_json(JOURNAL_DIR / f"{date_key}.json")


def list_daily_performance_journals(limit: int = 20) -> list[dict[str, Any]]:
    capped = max(1, min(100, int(limit)))
    paths = sorted(JOURNAL_DIR.glob("*.json"), reverse=True)[:capped]
    return [_read_json(path) for path in paths]


def _journal_is_due(now: datetime.datetime) -> bool:
    local_now = now.astimezone(KST)
    return is_market_trading_day("KR", local_now) and local_now.timetz() >= JOURNAL_TIME_KST


def _scheduler_loop(
    market_loader: Callable[[], dict[str, Any]],
    broker_activity_loader: Callable[[str], dict[str, Any]] | None,
) -> None:
    attempted_dates: set[str] = set()
    while not _scheduler_stop.is_set():
        now = datetime.datetime.now(KST)
        date_key = now.date().isoformat()
        path = JOURNAL_DIR / f"{date_key}.json"
        if _journal_is_due(now) and date_key not in attempted_dates and not path.exists():
            attempted_dates.add(date_key)
            generate_daily_performance_journal(
                date_key,
                market_loader=market_loader,
                broker_activity_loader=broker_activity_loader,
                generated_at=now,
            )
        _scheduler_stop.wait(30)


def start_daily_performance_journal_scheduler(
    market_loader: Callable[[], dict[str, Any]],
    broker_activity_loader: Callable[[str], dict[str, Any]] | None = None,
) -> None:
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(market_loader, broker_activity_loader),
        name="daily-performance-journal",
        daemon=True,
    )
    _scheduler_thread.start()


def stop_daily_performance_journal_scheduler() -> None:
    _scheduler_stop.set()
    thread = _scheduler_thread
    if thread is not None:
        thread.join(timeout=2)
