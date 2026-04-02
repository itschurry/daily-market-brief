from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import live_signal_engine as live_svc
from services import strategy_registry as registry_svc
from services import universe_builder as universe_svc


class LiveRuntimeArchitectureTests(unittest.TestCase):
    def test_strategy_registry_live_only_returns_enabled_approved(self):
        rows = registry_svc.list_strategies(live_only=True)
        self.assertGreaterEqual(len(rows), 1)
        self.assertTrue(all(item.get("enabled") for item in rows))
        self.assertTrue(all(item.get("approval_status") == "approved" for item in rows))

    def test_universe_builder_returns_rule_snapshot(self):
        snapshot = universe_svc.get_universe_snapshot("top_liquidity_200", market="KOSPI", refresh=True)
        self.assertEqual("top_liquidity_200", snapshot["rule_name"])
        self.assertEqual("KOSPI", snapshot["market"])
        self.assertGreaterEqual(snapshot["symbol_count"], 1)

    def test_live_signal_book_scans_registry_strategy(self):
        strategy = {
            "strategy_id": "kr_momentum_v1",
            "name": "KR Momentum v1",
            "enabled": True,
            "approval_status": "approved",
            "market": "KOSPI",
            "universe_rule": "top_liquidity_200",
            "scan_cycle": "5m",
            "params": {
                "market": "KOSPI",
                "max_positions": 5,
                "max_holding_days": 15,
                "rsi_min": 38.0,
                "rsi_max": 62.0,
                "volume_ratio_min": 1.0,
                "stop_loss_pct": 5.0,
                "take_profit_pct": None,
                "signal_interval": "1d",
                "signal_range": "6mo",
                "scan_limit": 10,
                "candidate_top_n": 5,
            },
            "risk_limits": {
                "max_positions": 5,
                "position_size_pct": 0.1,
                "daily_loss_limit_pct": 0.02,
                "min_liquidity": 100000,
                "max_spread_pct": 1.0,
            },
        }
        technical_snapshot = {
            "current_price": 71000.0,
            "close": 71000.0,
            "sma20": 68000.0,
            "sma60": 65000.0,
            "volume_ratio": 1.6,
            "volume_avg20": 2500000,
            "rsi14": 57.0,
            "macd": 5.0,
            "macd_signal": 1.0,
            "macd_hist": 4.0,
            "atr14_pct": 1.4,
            "spread_pct": 0.1,
        }
        with patch.object(live_svc, "list_strategies", return_value=[strategy]), \
             patch.object(live_svc, "get_universe_snapshot", return_value={
                 "rule_name": "top_liquidity_200",
                 "market": "KOSPI",
                 "symbol_count": 1,
                 "symbols": [{"code": "005930", "name": "삼성전자", "market": "KOSPI", "sector": "반도체"}],
             }), \
             patch.object(live_svc, "_compute_technical_snapshot", return_value=technical_snapshot):
            book = live_svc.build_live_signal_book(account={
                "positions": [],
                "orders": [],
                "equity_krw": 20_000_000,
                "cash_krw": 10_000_000,
                "cash_usd": 0,
                "fx_rate": 1300.0,
            }, refresh=True)

        self.assertEqual(1, book["count"])
        signal = book["signals"][0]
        self.assertEqual("kr_momentum_v1", signal["strategy_id"])
        self.assertEqual("entry", signal["signal_state"])
        self.assertTrue(signal["entry_allowed"])


if __name__ == "__main__":
    unittest.main()
