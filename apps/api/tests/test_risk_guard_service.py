from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from services.risk_guard_service import InvalidAccountSnapshotError, build_risk_guard_state
from services.trading_pipeline.decision import _risk_config, build_signal_book


class RiskGuardServiceTests(unittest.TestCase):
    def test_live_entries_fail_closed_without_exact_realized_pnl(self) -> None:
        state = build_risk_guard_state(
            account={
                "mode": "real",
                "equity_krw": 3_600_000,
                "positions": [],
                "orders": [],
            },
            cfg={
                "performance_starting_equity_krw": 3_700_000,
                "max_total_drawdown_pct": 3.0,
            },
            regime="neutral",
            risk_level="normal",
        )

        self.assertFalse(state["entry_allowed"])
        self.assertFalse(state["realized_pnl_available"])
        self.assertIn("realized_pnl_unavailable", state["reasons"])

    def test_exact_live_realized_loss_blocks_new_entries(self) -> None:
        account = {
            "mode": "real",
            "equity_krw": 3_600_000,
            "positions": [],
            "orders": [],
            "daily_realized_pnl_available": True,
            "daily_realized_pnl_date": "2026-08-20",
            "daily_realized_pnl_krw": -40_000,
            "daily_realized_trades": [{
                "date": "2026-08-20",
                "code": "001450",
                "realized_pnl_krw": -40_000,
            }],
        }
        with patch("services.risk_guard_service._today_kst", return_value="2026-08-20"):
            state = build_risk_guard_state(
                account=account,
                cfg={
                    "performance_starting_equity_krw": 3_700_000,
                    "daily_loss_limit_pct": 1.0,
                    "max_total_drawdown_pct": 3.0,
                },
                regime="neutral",
                risk_level="normal",
            )

        self.assertFalse(state["entry_allowed"])
        self.assertTrue(state["realized_pnl_available"])
        self.assertEqual(state["daily_realized_loss"], 40_000)
        self.assertEqual(state["daily_loss_left"], 0)
        self.assertEqual(state["loss_streak"], 1)
        self.assertIn("daily_loss_limit_reached", state["reasons"])

    def test_stale_live_realized_pnl_blocks_new_entries(self) -> None:
        account = {
            "mode": "real",
            "equity_krw": 3_700_000,
            "positions": [],
            "daily_realized_pnl_available": True,
            "daily_realized_pnl_date": "2026-08-19",
            "daily_realized_trades": [],
        }
        with patch("services.risk_guard_service._today_kst", return_value="2026-08-20"):
            state = build_risk_guard_state(
                account=account,
                cfg={"performance_starting_equity_krw": 3_700_000},
                regime="neutral",
                risk_level="normal",
            )

        self.assertFalse(state["entry_allowed"])
        self.assertIn("realized_pnl_unavailable", state["reasons"])

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
