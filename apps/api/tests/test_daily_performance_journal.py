from __future__ import annotations

import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from services.daily_performance_journal import _account_orders, _validate_date_key, build_daily_performance_journal


KST = ZoneInfo("Asia/Seoul")


class DailyPerformanceJournalTests(unittest.TestCase):
    def test_rejects_invalid_date_key(self) -> None:
        with self.assertRaises(ValueError):
            _validate_date_key("../../engine_state")

    def test_builds_daily_account_market_and_trade_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cycles_dir = Path(tmpdir) / "engine_cycles"
            journals_dir = Path(tmpdir) / "daily_performance"
            cycles_dir.mkdir()
            journals_dir.mkdir()
            buy = {
                "ts": "2026-07-16T00:15:00+00:00", "side": "buy", "status": "filled",
                "code": "000020", "market": "KOSPI", "quantity": 10,
                "filled_price_krw": 1000, "fee_krw": 2, "entry_plan_price": 990,
                "stop_loss_price": 950, "take_profit_price": 1100,
            }
            sell = {
                "ts": "2026-07-16T00:45:00+00:00", "side": "sell", "status": "filled",
                "code": "000020", "market": "KOSPI", "quantity": 10,
                "filled_price_krw": 1020, "fee_krw": 3, "realized_pnl_krw": 197,
                "note": "Auto-liquidation (trailing_profit_stop)",
            }
            cycles = [
                {
                    "started_at": "2026-07-15T23:50:00+00:00",
                    "account": {"mode": "paper", "equity_krw": 5_000_000, "starting_equity_krw": 5_000_000, "orders": []},
                    "executed_buys": [], "skip_reason_counts": {}, "blocked_reason_counts": {},
                },
                {
                    "started_at": "2026-07-16T06:39:00+00:00",
                    "account": {
                        "mode": "paper", "equity_krw": 5_000_195, "cash_krw": 5_000_195,
                        "market_value_krw": 0, "starting_equity_krw": 5_000_000,
                        "positions": [], "orders": [sell, buy],
                    },
                    "executed_buys": [{"code": "000020", "name": "동화약품", "expected_value": 0.7, "strategy_type": "scanner"}],
                    "skip_reason_counts": {"entry_price_chased": 1},
                    "blocked_reason_counts": {},
                    "rotation_summary": {"attempted_count": 0, "executed_count": 0},
                },
            ]
            path = cycles_dir / "2026-07-16.jsonl"
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in cycles), encoding="utf-8")

            with (
                patch("services.daily_performance_journal.ENGINE_CYCLES_DIR", cycles_dir),
                patch("services.daily_performance_journal.JOURNAL_DIR", journals_dir),
                patch("services.daily_performance_journal.load_engine_state", return_value={"current_config": {"markets": ["KOSPI"]}}),
            ):
                result = build_daily_performance_journal(
                    "2026-07-16",
                    market_payload={"kospi_history": [{"date": "2026-07-16", "close": 6820.6, "pct": -6.37}]},
                    generated_at=datetime.datetime(2026, 7, 16, 15, 40, tzinfo=KST),
                )

        self.assertEqual(result["account"]["net_pnl_krw"], 195.0)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["trading"]["round_trip_count"], 1)
        self.assertEqual(result["trading"]["closed_trade_count"], 1)
        self.assertEqual(len(result["trading"]["same_day_round_trips"]), 1)
        self.assertEqual(result["trading"]["carry_in_exits"], [])
        self.assertEqual(result["trading"]["trades"][0]["name"], "동화약품")
        self.assertEqual(result["trading"]["trades"][0]["holding_seconds"], 1800)
        self.assertEqual(result["market"]["kospi_return_pct"], -6.37)
        self.assertEqual(result["diagnostics"]["skip_reason_counts"], {"entry_price_chased": 1})

    def test_separates_carry_in_exit_open_close_and_follow_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cycles_dir = root / "engine_cycles"
            accounts_dir = root / "accounts"
            journals_dir = root / "daily_performance"
            cycles_dir.mkdir()
            accounts_dir.mkdir()
            journals_dir.mkdir()
            carry_buy = {"ts": "2026-07-20T00:30:00+00:00", "side": "buy", "status": "filled", "code": "465770", "market": "KOSPI", "quantity": 10, "filled_price_krw": 1000, "fee_krw": 2}
            carry_sell = {"ts": "2026-07-21T00:10:00+00:00", "side": "sell", "status": "filled", "code": "465770", "market": "KOSPI", "quantity": 10, "filled_price_krw": 1200, "fee_krw": 20, "realized_pnl_krw": 1980, "note": "take_profit"}
            open_buy = {"ts": "2026-07-21T00:30:00+00:00", "side": "buy", "status": "filled", "code": "483650", "market": "KOSPI", "quantity": 2, "filled_price_krw": 2000, "fee_krw": 1}
            next_day_sell = {"ts": "2026-07-22T00:10:00+00:00", "side": "sell", "status": "filled", "code": "483650", "market": "KOSPI", "quantity": 2, "filled_price_krw": 1900, "fee_krw": 4, "realized_pnl_krw": -204, "note": "stop_loss"}
            start = {"mode": "paper", "equity_krw": 11_980, "cash_krw": 11_980, "starting_equity_krw": 10_000, "positions": [], "orders": [carry_sell, carry_buy]}
            end = {"mode": "paper", "equity_krw": 12_079, "cash_krw": 7_979, "market_value_krw": 4_100, "starting_equity_krw": 10_000, "positions": [{"code": "483650", "market": "KOSPI", "quantity": 2, "entry_ts": open_buy["ts"], "avg_price_krw": 2000, "last_price_krw": 2050, "market_value_krw": 4100, "unrealized_pnl_krw": 100, "unrealized_pnl_pct": 2.5}], "orders": [open_buy, carry_sell, carry_buy]}
            previous_journal = {
                "schema_version": 2,
                "date": "2026-07-20",
                "account": {"ending_equity_krw": 10_500},
                "trading": {"open_at_close": [{"code": "465770", "name": "STX그린로지스", "quantity": 10, "close_price_krw": 1050, "market_value_krw": 10_500}]},
            }
            rows = [
                {"started_at": "2026-07-20T23:50:00+00:00", "account": start},
                {"started_at": "2026-07-21T06:39:00+00:00", "account": end, "executed_buys": [{"code": "483650", "name": "달바글로벌"}]},
                {"started_at": "2026-07-21T23:00:00+00:00", "account": {**end, "equity_krw": 999_999}},
            ]
            (cycles_dir / "2026-07-21.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            (journals_dir / "2026-07-20.json").write_text(json.dumps(previous_journal, ensure_ascii=False), encoding="utf-8")
            (accounts_dir / "simulated_account_state.json").write_text(json.dumps({**end, "orders": [next_day_sell, open_buy, carry_sell, carry_buy]}), encoding="utf-8")
            with (
                patch("services.daily_performance_journal.ENGINE_CYCLES_DIR", cycles_dir),
                patch("services.daily_performance_journal.JOURNAL_DIR", journals_dir),
                patch("services.daily_performance_journal.RUNTIME_DIR", root),
                patch("services.daily_performance_journal.load_engine_state", return_value={}),
            ):
                result = build_daily_performance_journal("2026-07-21", market_payload={"kospi_history": [{"date": "2026-07-21", "close": 1, "pct": 1}]})

        self.assertEqual(result["account"]["starting_equity_krw"], 10_500)
        self.assertEqual(result["account"]["ending_equity_krw"], 12_079)
        self.assertEqual(result["account"]["net_pnl_krw"], 1_579)
        self.assertEqual(len(result["trading"]["carry_in_exits"]), 1)
        self.assertEqual(len(result["trading"]["open_at_close"]), 1)
        self.assertEqual(result["trading"]["open_at_close"][0]["position_origin"], "opened_today")
        self.assertEqual(result["follow_up"]["outcomes"][0]["status"], "closed")
        self.assertEqual(result["follow_up"]["outcomes"][0]["realized_pnl_krw"], -204)
        self.assertEqual(result["pnl_attribution"]["carry_in_exit_contribution_krw"], 1_480)
        self.assertEqual(result["pnl_attribution"]["unattributed_krw"], 0)
        self.assertEqual(result["diagnostics"]["engine_cycle_count"], 2)

    def test_live_journal_uses_kis_fills_and_realized_profit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cycles_dir = root / "engine_cycles"
            journals_dir = root / "daily_performance"
            cycles_dir.mkdir()
            journals_dir.mkdir()
            submitted_buy = {
                "order_id": "1001", "timestamp": "2026-08-05T00:19:45+00:00",
                "side": "buy", "code": "006340", "quantity": 16,
                "status": "submitted", "lifecycle_state": "submitted",
            }
            filled_buy = {
                **submitted_buy,
                "filled_at": "2026-08-05T00:19:45+00:00",
                "filled_price_krw": 15760,
                "lifecycle_state": "filled",
                "execution_status": "filled",
            }
            self.assertEqual(len(_account_orders({"orders": [submitted_buy, filled_buy]})), 1)
            cycles = [
                {
                    "started_at": "2026-08-04T23:50:00+00:00",
                    "account": {
                        "mode": "real", "equity_krw": 3_758_490, "cash_krw": 3_758_490,
                        "positions": [], "orders": [],
                    },
                },
                {
                    "started_at": "2026-08-05T06:39:00+00:00",
                    "account": {
                        "mode": "real", "equity_krw": 3_757_330, "cash_krw": 3_757_330,
                        "market_value_krw": 0, "positions": [], "orders": [submitted_buy, filled_buy],
                    },
                    "executed_buys": [{"code": "006340", "name": "대원전선"}],
                    "executed_sells": [{"code": "006340", "reason": "본전보호"}],
                },
            ]
            (cycles_dir / "2026-08-05.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in cycles),
                encoding="utf-8",
            )
            broker_activity = {
                "fills": {
                    "orders": [
                        {
                            "order_id": "1001", "filled_at": "2026-08-05T09:19:45+09:00",
                            "side": "buy", "code": "006340", "name": "대원전선", "market": "KOSPI",
                            "quantity": 16, "filled_price_krw": 15760, "notional_krw": 252160,
                            "lifecycle_state": "filled",
                        },
                        {
                            "order_id": "1002", "filled_at": "2026-08-05T09:39:49+09:00",
                            "side": "sell", "code": "006340", "name": "대원전선", "market": "KOSPI",
                            "quantity": 16, "filled_price_krw": 15720, "notional_krw": 251520,
                            "execution_status": "filled",
                        },
                    ],
                    "summary": {"fees_and_tax_krw": 520},
                },
                "profits": {
                    "trades": [{
                        "date": "2026-08-05", "code": "006340", "name": "대원전선", "market": "KOSPI",
                        "quantity": 16, "entry_price_krw": 15760, "exit_price_krw": 15720,
                        "buy_quantity": 16, "buy_notional_krw": 252160, "sell_notional_krw": 251520,
                        "realized_pnl_krw": -1160, "total_cost_krw": 520,
                    }],
                },
            }
            with (
                patch("services.daily_performance_journal.ENGINE_CYCLES_DIR", cycles_dir),
                patch("services.daily_performance_journal.JOURNAL_DIR", journals_dir),
                patch("services.daily_performance_journal.RUNTIME_DIR", root),
                patch("services.daily_performance_journal.load_engine_state", return_value={}),
            ):
                result = build_daily_performance_journal(
                    "2026-08-05",
                    market_payload={"kospi_history": [{"date": "2026-08-05", "close": 1, "pct": 3.76}]},
                    broker_activity=broker_activity,
                )

        self.assertEqual(result["account"]["net_pnl_krw"], -1160)
        self.assertEqual(result["account"]["fees_krw"], 520)
        self.assertEqual(result["trading"]["buy_count"], 1)
        self.assertEqual(result["trading"]["sell_count"], 1)
        self.assertEqual(result["trading"]["round_trip_count"], 1)
        self.assertEqual(result["trading"]["trades"][0]["realized_pnl_krw"], -1160)
        self.assertEqual(result["trading"]["trades"][0]["exit_reason"], "본전보호")
        self.assertEqual(result["pnl_attribution"]["unattributed_krw"], 0)
        self.assertEqual(result["diagnostics"]["trade_ledger_source"], "kis")


if __name__ == "__main__":
    unittest.main()
