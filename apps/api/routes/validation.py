from __future__ import annotations

from services.backtest_params_store import (
    load_persisted_validation_settings,
    reset_persisted_validation_settings,
    save_persisted_validation_settings,
)
from services.validation_service import (
    run_backtest_with_extended_metrics,
    run_validation_diagnostics,
    run_walk_forward_validation,
)


def handle_validation_backtest(query: dict[str, list[str]]) -> tuple[int, dict]:
    try:
        return 200, run_backtest_with_extended_metrics(query)
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_validation_walk_forward(query: dict[str, list[str]]) -> tuple[int, dict]:
    try:
        return 200, run_walk_forward_validation(query)
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_validation_diagnostics(query: dict[str, list[str]]) -> tuple[int, dict]:
    try:
        return 200, run_validation_diagnostics(query)
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_validation_settings_get() -> tuple[int, dict]:
    try:
        return 200, load_persisted_validation_settings()
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_validation_settings_save(payload: dict) -> tuple[int, dict]:
    try:
        return 200, save_persisted_validation_settings(payload)
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_validation_settings_reset() -> tuple[int, dict]:
    try:
        return 200, reset_persisted_validation_settings()
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}
