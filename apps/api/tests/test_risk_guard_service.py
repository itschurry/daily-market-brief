from __future__ import annotations

import sys
import unittest
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from services.risk_guard_service import InvalidAccountSnapshotError, build_risk_guard_state
from services.trading_pipeline.decision import _risk_config, build_signal_book


class RiskGuardServiceTests(unittest.TestCase):
    def test_percent_risk_limits_are_not_reinterpreted_as_ratios(self) -> None:
        config = _risk_config({
            "allocation_mode": "diversified",
            "daily_loss_limit_pct": 1.0,
            "max_total_drawdown_pct": 3.0,
            "performance_starting_equity_krw": 3_758_914,
            "max_symbol_weight_pct": 1.0,
            "max_sector_weight_pct": 35.0,
            "max_market_exposure_pct": 40.0,
        })

        self.assertEqual(config["daily_loss_limit_pct"], 1.0)
        self.assertEqual(config["max_total_drawdown_pct"], 3.0)
        self.assertEqual(config["performance_starting_equity_krw"], 3_758_914)
        self.assertEqual(config["max_symbol_weight_pct"], 1.0)

    def test_bluechip_position_ratio_is_converted_to_percent(self) -> None:
        config = _risk_config({
            "allocation_mode": "concentrated",
            "max_symbol_weight_pct": 20.0,
            "bluechip_max_symbol_position_ratio": 0.2,
        })

        self.assertEqual(config["max_symbol_weight_pct"], 20.0)

    def test_invalid_equity_fails_instead_of_reporting_false_drawdown(self) -> None:
        invalid_accounts = [
            {},
            {"equity_krw": None},
            {"equity_krw": 0},
            {"equity_krw": -1},
            {"equity_krw": "not-a-number"},
            {"equity_krw": float("nan")},
            {"equity_krw": float("inf")},
            {"ok": False, "equity_krw": 5_000_000},
            {"error": "kis_account_lookup_failed", "equity_krw": 5_000_000},
        ]

        for account in invalid_accounts:
            with self.subTest(account=account):
                with self.assertRaises(InvalidAccountSnapshotError):
                    build_risk_guard_state(
                        account=account,
                        cfg={"performance_starting_equity_krw": 5_000_000},
                        regime="neutral",
                        risk_level="normal",
                    )

    def test_signal_book_fails_before_processing_candidates_when_account_is_missing(self) -> None:
        with self.assertRaisesRegex(InvalidAccountSnapshotError, "account_snapshot_invalid"):
            build_signal_book(markets=["KOSPI"], cfg={}, account=None)

    def test_total_drawdown_blocks_new_entries(self) -> None:
        state = build_risk_guard_state(
            account={"equity_krw": 3_750_000, "positions": [], "orders": []},
            cfg={
                "performance_starting_equity_krw": 5_000_000,
                "max_total_drawdown_pct": 10.0,
            },
            regime="neutral",
            risk_level="normal",
        )

        self.assertFalse(state["entry_allowed"])
        self.assertIn("total_drawdown_limit_reached", state["reasons"])
        self.assertEqual(state["total_drawdown_pct"], 25.0)

    def test_total_drawdown_below_limit_allows_entry(self) -> None:
        state = build_risk_guard_state(
            account={"equity_krw": 4_750_000, "positions": [], "orders": []},
            cfg={
                "performance_starting_equity_krw": 5_000_000,
                "max_total_drawdown_pct": 10.0,
            },
            regime="neutral",
            risk_level="normal",
        )

        self.assertTrue(state["entry_allowed"])
        self.assertNotIn("total_drawdown_limit_reached", state["reasons"])


if __name__ == "__main__":
    unittest.main()
