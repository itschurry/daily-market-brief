"""System mode exposure for API/UI."""

from __future__ import annotations

import os

from modes import LIVE_DISABLED, LIVE_READY, PAPER, REPORT, SUPPORTED_MODES, normalize_mode


def _fallback_mode_from_execution_env() -> str:
    execution_mode = str(os.getenv("EXECUTION_MODE", "") or "").strip().lower()
    if execution_mode == "live":
        return LIVE_READY
    if execution_mode == REPORT:
        return REPORT
    if execution_mode == PAPER:
        return PAPER
    return LIVE_DISABLED


def get_mode_status() -> dict:
    configured = str(os.getenv("AUTO_INVEST_MODE", "") or "").strip().lower()
    default_mode = _fallback_mode_from_execution_env()
    current = normalize_mode(configured, default=default_mode)
    return {
        "ok": True,
        "current_mode": current,
        "supported_modes": list(SUPPORTED_MODES),
    }
