"""몬테카를로 파라미터 최적화 엔진.

부트스트랩 또는 GBM 방식으로 미래 가격 경로를 시뮬레이션하고,
손절/익절/기간만료 전략의 최적 파라미터를 탐색한다.
"""
from __future__ import annotations

import datetime
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger


@dataclass
class SimulationConfig:
    """몬테카를로 시뮬레이션 설정"""
    n_simulations: int = 5000
    lookback_days: int = 252
    validation_days: int = 63
    simulation_days: int = 20
    method: str = "bootstrap"   # "bootstrap" | "gbm"
    random_seed: int = 42


@dataclass
class ParamGrid:
    """최적화할 파라미터 탐색 범위"""
    stop_loss_pct: list[float] = field(default_factory=lambda: [3.0, 5.0, 7.0, 10.0])
    take_profit_pct: list[float] = field(default_factory=lambda: [6.0, 10.0, 15.0, 20.0])
    max_holding_days: list[int] = field(default_factory=lambda: [5, 10, 20, 30])
    rsi_min: list[float] = field(default_factory=lambda: [30.0, 35.0, 40.0])
    rsi_max: list[float] = field(default_factory=lambda: [70.0, 75.0, 80.0])


@dataclass
class OptimizationResult:
    """최적화 결과"""
    symbol: str
    market: str
    best_params: dict
    sharpe_ratio: float
    win_rate: float
    avg_return_pct: float
    max_drawdown_pct: float
    n_trades: float
    validation_sharpe: float
    optimized_at: str
    is_reliable: bool


# 클램핑 범위
_STOP_LOSS_RANGE = (2.0, 15.0)
_TAKE_PROFIT_RANGE = (4.0, 30.0)
_HOLDING_DAYS_RANGE = (3, 60)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def generate_price_paths(
    returns: np.ndarray,
    n_simulations: int,
    simulation_days: int,
    method: str = "bootstrap",
    seed: int = 42,
) -> np.ndarray:
    """과거 수익률로 미래 가격 경로를 생성한다.

    Returns:
        shape (n_simulations, simulation_days) — 시작가 1.0 기준 누적 경로
    """
    rng = np.random.default_rng(seed)
    if method == "bootstrap":
        sampled = rng.choice(returns, size=(n_simulations, simulation_days), replace=True)
        paths = np.cumprod(1.0 + sampled, axis=1)
    else:  # gbm
        mu = float(np.mean(returns))
        sigma = float(np.std(returns))
        dt = 1.0
        Z = rng.standard_normal((n_simulations, simulation_days))
        daily_rets = np.exp((mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * Z)
        paths = np.cumprod(daily_rets, axis=1)
    return paths


def simulate_strategy(
    paths: np.ndarray,
    stop_loss_pct: float,
    take_profit_pct: float,
    max_holding_days: int,
) -> dict:
    """가격 경로에 매매 전략을 적용하고 성과 지표를 반환한다.

    진입: 경로 시작점(= 1.0)에서 매수
    청산: 익절 / 손절 / 기간만료 중 먼저 충족되는 조건
    """
    n_sim, n_days = paths.shape
    sl = 1.0 - stop_loss_pct / 100.0
    tp = 1.0 + take_profit_pct / 100.0
    hold_cap = min(max_holding_days, n_days)

    # 각 경로에서 첫 번째로 손절/익절/기간만료 조건이 발생하는 날 찾기
    hit_sl = paths <= sl          # (n_sim, n_days)
    hit_tp = paths >= tp

    exit_returns = np.empty(n_sim)
    holding_days_arr = np.empty(n_sim)

    for i in range(n_sim):
        sl_hit = hit_sl[i, :hold_cap].any()
        tp_hit = hit_tp[i, :hold_cap].any()
        sl_idx = int(np.argmax(hit_sl[i, :hold_cap])) if sl_hit else hold_cap
        tp_idx = int(np.argmax(hit_tp[i, :hold_cap])) if tp_hit else hold_cap

        exit_day = min(sl_idx, tp_idx)
        if exit_day >= hold_cap:
            exit_day = hold_cap - 1

        exit_returns[i] = paths[i, exit_day] - 1.0
        holding_days_arr[i] = exit_day + 1

    avg_holding = float(np.mean(holding_days_arr))
    win_mask = exit_returns > 0
    win_rate = float(win_mask.mean())
    avg_return = float(np.mean(exit_returns)) * 100.0
    std_return = float(np.std(exit_returns))

    # 연율화 샤프지수
    if std_return > 1e-9 and avg_holding > 0:
        sharpe = (float(np.mean(exit_returns)) / std_return) * np.sqrt(252.0 / avg_holding)
    else:
        sharpe = 0.0

    # 최대낙폭: 경로별 고점 대비 최저점
    cummax = np.maximum.accumulate(paths[:, :hold_cap], axis=1)
    drawdowns = (paths[:, :hold_cap] - cummax) / cummax
    max_dd = float(np.min(drawdowns)) * 100.0

    return {
        "win_rate": win_rate,
        "avg_return_pct": avg_return,
        "sharpe_ratio": sharpe,
        "max_drawdown_pct": max_dd,
        "avg_holding_days": avg_holding,
        "n_profitable": int(win_mask.sum()),
        "n_total": n_sim,
    }


def optimize_params(
    symbol: str,
    market: str,
    price_history: list[dict[str, Any]],
    param_grid: ParamGrid,
    sim_config: SimulationConfig,
) -> OptimizationResult | None:
    """단일 종목에 대해 파라미터 그리드 탐색을 수행한다."""
    closes = [float(r["close"]) for r in price_history if r.get("close") is not None]
    if len(closes) < sim_config.lookback_days + sim_config.validation_days:
        logger.debug("{}/{}: 데이터 부족 ({} < {})", symbol, market, len(closes),
                     sim_config.lookback_days + sim_config.validation_days)
        return None

    all_returns = np.diff(np.array(closes)) / np.array(closes[:-1])
    train_returns = all_returns[-sim_config.lookback_days - sim_config.validation_days:
                                -sim_config.validation_days]
    val_returns = all_returns[-sim_config.validation_days:]

    if len(train_returns) < 30:
        return None

    train_paths = generate_price_paths(
        train_returns, sim_config.n_simulations, sim_config.simulation_days,
        sim_config.method, sim_config.random_seed,
    )

    best_sharpe = -np.inf
    best_params: dict = {}
    best_metrics: dict = {}

    for sl, tp, hd, rsi_lo, rsi_hi in itertools.product(
        param_grid.stop_loss_pct,
        param_grid.take_profit_pct,
        param_grid.max_holding_days,
        param_grid.rsi_min,
        param_grid.rsi_max,
    ):
        # 비현실적 조합 제거
        if tp < sl * 1.5:
            continue
        if rsi_lo >= rsi_hi:
            continue

        metrics = simulate_strategy(train_paths, sl, tp, hd)
        if metrics["sharpe_ratio"] > best_sharpe:
            best_sharpe = metrics["sharpe_ratio"]
            best_params = {
                "stop_loss_pct": _clamp(sl, *_STOP_LOSS_RANGE),
                "take_profit_pct": _clamp(tp, *_TAKE_PROFIT_RANGE),
                "max_holding_days": int(_clamp(hd, *_HOLDING_DAYS_RANGE)),
                "rsi_min": rsi_lo,
                "rsi_max": rsi_hi,
            }
            best_metrics = metrics

    if not best_params:
        return None

    # 검증 기간으로 과적합 체크
    val_paths = generate_price_paths(
        val_returns, sim_config.n_simulations, sim_config.simulation_days,
        sim_config.method, sim_config.random_seed + 1,
    )
    val_metrics = simulate_strategy(
        val_paths,
        best_params["stop_loss_pct"],
        best_params["take_profit_pct"],
        best_params["max_holding_days"],
    )
    validation_sharpe = val_metrics["sharpe_ratio"]

    return OptimizationResult(
        symbol=symbol,
        market=market,
        best_params=best_params,
        sharpe_ratio=best_sharpe,
        win_rate=best_metrics.get("win_rate", 0.0),
        avg_return_pct=best_metrics.get("avg_return_pct", 0.0),
        max_drawdown_pct=best_metrics.get("max_drawdown_pct", 0.0),
        n_trades=best_metrics.get("avg_holding_days", 0.0),
        validation_sharpe=validation_sharpe,
        optimized_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        is_reliable=validation_sharpe > 0,
    )


def run_portfolio_optimization(
    symbols: list[tuple[str, str]],
    price_data: dict[str, list[dict[str, Any]]],
    param_grid: ParamGrid | None = None,
    sim_config: SimulationConfig | None = None,
) -> list[OptimizationResult]:
    """여러 종목에 대해 병렬로 optimize_params를 실행한다."""
    if param_grid is None:
        param_grid = ParamGrid()
    if sim_config is None:
        sim_config = SimulationConfig()

    results: list[OptimizationResult] = []
    total = len(symbols)

    def _task(code: str, market: str) -> OptimizationResult | None:
        history = price_data.get(code) or []
        if not history:
            logger.debug("{}/{}: 가격 데이터 없음, 스킵", code, market)
            return None
        try:
            return optimize_params(code, market, history, param_grid, sim_config)
        except Exception as exc:
            logger.warning("{}/{}: 최적화 실패 — {}", code, market, exc)
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_task, code, market): (code, market)
                   for code, market in symbols}
        done = 0
        for future in as_completed(futures):
            code, market = futures[future]
            done += 1
            result = future.result()
            if result is not None:
                results.append(result)
                logger.info("[{}/{}] {} ({}) — 샤프={:.2f}, 신뢰={}",
                            done, total, code, market,
                            result.sharpe_ratio, result.is_reliable)
            else:
                logger.info("[{}/{}] {} ({}) — 스킵", done, total, code, market)

    return results
