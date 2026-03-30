"""Shared reliability thresholds for optimizer, execution, calibration, and reporting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from services.reliability_policy import (
    BORDERLINE_REASONS,
    MAX_DRAWDOWN_FILTER_PCT,
    MAX_DRAWDOWN_RELIABLE_PCT,
    MIN_RELIABLE_TRAIN_TRADES,
    MIN_TRAIN_TRADES,
    MIN_VALIDATION_SHARPE_FILTER,
    MIN_VALIDATION_SHARPE_RELIABLE,
    MIN_VALIDATION_SIGNALS,
    classify_optimization_reliability,
)


@dataclass(frozen=True)
class ValidationReliabilityAssessment:
    label: str
    reason: str
    trade_count: int
    validation_signals: int
    validation_sharpe: float
    max_drawdown_pct: float | None
    passes_minimum_gate: bool
    is_reliable: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WalkForwardReliabilityAssessment:
    label: str
    trade_count: int
    profit_factor: float
    sharpe: float
    total_return_pct: float
    positive_window_ratio: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def reliability_thresholds() -> dict[str, float]:
    return {
        "min_train_trades": MIN_TRAIN_TRADES,
        "min_reliable_train_trades": MIN_RELIABLE_TRAIN_TRADES,
        "min_validation_signals": MIN_VALIDATION_SIGNALS,
        "min_sharpe_filter": MIN_VALIDATION_SHARPE_FILTER,
        "min_sharpe_reliable": MIN_VALIDATION_SHARPE_RELIABLE,
        "max_drawdown_filter": MAX_DRAWDOWN_FILTER_PCT,
        "max_drawdown_reliable": MAX_DRAWDOWN_RELIABLE_PCT,
    }


def assess_validation_reliability(
    *,
    trade_count: int,
    validation_signals: int,
    validation_sharpe: float,
    max_drawdown_pct: float | None = None,
) -> ValidationReliabilityAssessment:
    trade_count = max(0, int(trade_count or 0))
    validation_signals = max(0, int(validation_signals or 0))
    validation_sharpe = _to_float(validation_sharpe, 0.0)
    max_drawdown = None if max_drawdown_pct is None else _to_float(max_drawdown_pct, 0.0)

    is_reliable, reason = classify_optimization_reliability(
        trade_count=trade_count,
        validation_signals=validation_signals,
        validation_sharpe=validation_sharpe,
        max_drawdown_pct=_to_float(max_drawdown, 0.0) if max_drawdown is not None else 0.0,
    )

    if is_reliable:
        label = "high"
        passes_minimum_gate = True
    elif reason in BORDERLINE_REASONS:
        label = "medium"
        passes_minimum_gate = True
    elif reason in {"excessive_drawdown", "weak_validation_sharpe"}:
        label = "low"
        passes_minimum_gate = False
    else:
        label = "insufficient"
        passes_minimum_gate = False

    return ValidationReliabilityAssessment(
        label=label,
        reason=reason,
        trade_count=trade_count,
        validation_signals=validation_signals,
        validation_sharpe=round(validation_sharpe, 4),
        max_drawdown_pct=max_drawdown,
        passes_minimum_gate=passes_minimum_gate,
        is_reliable=is_reliable,
    )


def classify_walk_forward_reliability(
    *,
    trade_count: int,
    profit_factor: float,
    sharpe: float,
    total_return_pct: float,
    positive_window_ratio: float,
) -> WalkForwardReliabilityAssessment:
    trade_count = max(0, int(trade_count or 0))
    profit_factor = _to_float(profit_factor, 0.0)
    sharpe = _to_float(sharpe, 0.0)
    total_return_pct = _to_float(total_return_pct, 0.0)
    positive_window_ratio = _to_float(positive_window_ratio, 0.0)

    label = "low"
    if trade_count < MIN_VALIDATION_SIGNALS:
        label = "insufficient"
    elif total_return_pct <= 0.0 or profit_factor < 1.0 or sharpe < MIN_VALIDATION_SHARPE_FILTER:
        label = "low"
    elif (
        trade_count >= MIN_TRAIN_TRADES
        and profit_factor >= 1.3
        and sharpe >= 0.75
        and positive_window_ratio >= 0.6
    ):
        label = "high"
    elif (
        trade_count >= 12
        and profit_factor >= 1.15
        and sharpe >= MIN_VALIDATION_SHARPE_RELIABLE
        and positive_window_ratio >= 0.5
    ):
        label = "medium"

    return WalkForwardReliabilityAssessment(
        label=label,
        trade_count=trade_count,
        profit_factor=round(profit_factor, 4),
        sharpe=round(sharpe, 4),
        total_return_pct=round(total_return_pct, 4),
        positive_window_ratio=round(positive_window_ratio, 4),
    )
