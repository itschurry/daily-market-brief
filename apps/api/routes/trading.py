"""Thin API route handlers delegating to execution service."""

from __future__ import annotations

from services.execution_service import _current_execution_mode
from services.runtime_account_cache import read_cached_live_runtime_account
from services.runtime_execution_service import get_execution_service


def _parse_limit(query: dict[str, list[str]], default: int, minimum: int = 1, maximum: int = 500) -> int:
    raw = (query.get("limit", [str(default)])[0] or str(default)).strip()
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _compact_cycle_summary(summary: object) -> dict:
    if not isinstance(summary, dict):
        return {}
    keep_keys = {
        "ok",
        "cycle_type",
        "cycle_id",
        "started_at",
        "finished_at",
        "ran_at",
        "executed_buy_count",
        "executed_sell_count",
        "candidate_counts_by_market",
        "blocked_reason_counts",
        "rotation_summary",
        "skip_reason_counts",
        "market_stats",
        "closed_markets",
        "risk_guard_state",
        "validation_gate_summary",
        "pnl_snapshot",
        "error",
    }
    compact = {key: summary[key] for key in keep_keys if key in summary}
    skipped = summary.get("skipped")
    compact["skipped_count"] = len(skipped) if isinstance(skipped, list) else 0
    return compact


def _compact_engine_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    account = payload.get("account") if isinstance(payload.get("account"), dict) else {}
    state_keys = {
        "engine_state",
        "running",
        "execution_mode",
        "started_at",
        "paused_at",
        "stopped_at",
        "last_run_at",
        "next_run_at",
        "last_success_at",
        "last_error",
        "last_error_at",
        "last_exit_check_at",
        "last_exit_error",
        "latest_cycle_id",
        "today_order_counts",
        "order_failure_summary",
        "today_realized_pnl",
        "current_equity",
        "validation_policy",
        "current_config",
        "config",
    }
    account_keys = {
        "ok",
        "mode",
        "base_currency",
        "cash_krw",
        "market_value_krw",
        "equity_krw",
        "starting_equity_krw",
        "realized_pnl_krw",
        "unrealized_pnl_krw",
        "fx_rate",
        "updated_at",
        "error",
    }
    compact_state = {key: state[key] for key in state_keys if key in state}
    compact_state["last_summary"] = _compact_cycle_summary(state.get("last_summary"))
    compact_state["last_exit_summary"] = _compact_cycle_summary(state.get("last_exit_summary"))
    compact_state["execution_mode"] = compact_state.get("execution_mode") or payload.get("execution_mode")
    positions = account.get("positions") if isinstance(account.get("positions"), list) else []
    compact_account = {key: account[key] for key in account_keys if key in account}
    compact_account["positions"] = [
        {
            key: item.get(key)
            for key in (
                "code",
                "name",
                "market",
                "currency",
                "quantity",
                "avg_price_local",
                "last_price_local",
                "market_value_krw",
                "unrealized_pnl_krw",
                "unrealized_pnl_pct",
                "orderable_quantity",
            )
            if isinstance(item, dict) and key in item
        }
        for item in positions
        if isinstance(item, dict)
    ]
    compact_payload = {
        "ok": payload.get("ok", True),
        "execution_mode": payload.get("execution_mode") or compact_state.get("execution_mode"),
        "state": compact_state,
        "account": compact_account,
    }
    for key in ("account_available", "account_error"):
        if key in payload:
            compact_payload[key] = payload[key]
    return compact_payload


def _latest_account_snapshot_payload() -> dict:
    cached_account = read_cached_live_runtime_account()
    if cached_account:
        return cached_account
    return {"ok": False, "error": "live_account_state_unavailable"}


def handle_runtime_account(refresh_quotes: bool) -> tuple[int, dict]:
    if not refresh_quotes and _current_execution_mode() == "live":
        payload = _latest_account_snapshot_payload()
        return (200 if payload.get("ok") else 503), payload
    return get_execution_service().runtime_account(refresh_quotes)


def handle_runtime_order(payload: dict) -> tuple[int, dict]:
    return get_execution_service().runtime_order(payload)


def handle_runtime_reset(payload: dict) -> tuple[int, dict]:
    return get_execution_service().runtime_reset(payload)


def handle_runtime_auto_invest(payload: dict) -> tuple[int, dict]:
    return get_execution_service().runtime_auto_invest(payload)


def handle_runtime_engine_start(payload: dict) -> tuple[int, dict]:
    status, result = get_execution_service().runtime_engine_start(payload)
    return status, _compact_engine_payload(result)


def handle_runtime_engine_stop() -> tuple[int, dict]:
    status, result = get_execution_service().runtime_engine_stop()
    return status, _compact_engine_payload(result)


def handle_runtime_engine_pause() -> tuple[int, dict]:
    status, result = get_execution_service().runtime_engine_pause()
    return status, _compact_engine_payload(result)


def handle_runtime_engine_resume() -> tuple[int, dict]:
    status, result = get_execution_service().runtime_engine_resume()
    return status, _compact_engine_payload(result)


def handle_runtime_engine_status() -> tuple[int, dict]:
    status, payload = get_execution_service().runtime_engine_status()
    return status, _compact_engine_payload(payload)


def handle_runtime_engine_cycles(query: dict[str, list[str]]) -> tuple[int, dict]:
    limit = _parse_limit(query, default=50, maximum=300)
    return get_execution_service().runtime_engine_cycles(limit)


def handle_runtime_orders(query: dict[str, list[str]]) -> tuple[int, dict]:
    limit = _parse_limit(query, default=100, maximum=500)
    return get_execution_service().runtime_orders(limit)


def handle_runtime_account_history(query: dict[str, list[str]]) -> tuple[int, dict]:
    limit = _parse_limit(query, default=100, maximum=500)
    return get_execution_service().runtime_account_history(limit)


def handle_runtime_history_clear(payload: dict) -> tuple[int, dict]:
    return get_execution_service().runtime_history_clear(payload)


def handle_runtime_workflow(query: dict[str, list[str]]) -> tuple[int, dict]:
    limit = _parse_limit(query, default=120, maximum=500)
    return get_execution_service().runtime_workflow(limit)
