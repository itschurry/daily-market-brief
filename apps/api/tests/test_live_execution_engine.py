from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from broker.execution_engine import EngineConfig, LiveBrokerExecutionEngine
from broker.kis_client import KISLedgerCapacityError, KISRequestAuditError


class LiveBrokerExecutionEngineTests(unittest.TestCase):
    def test_get_account_includes_exact_daily_realized_pnl(self) -> None:
        client = Mock()
        client.get_balance.return_value = {
            "mode": "real",
            "equity_krw": 3_600_000,
        }
        client.get_domestic_period_trade_profit.return_value = {
            "date": "2026-08-20",
            "trades": [{
                "date": "2026-08-20",
                "code": "001450",
                "realized_pnl_krw": -12_000,
            }],
            "summary": {"realized_pnl_krw": -12_000},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LiveBrokerExecutionEngine(
                kis_client=client,
                quote_provider=Mock(),
                fx_provider=Mock(),
                config=EngineConfig(state_path=Path(tmpdir) / "live.json"),
            )
            with patch(
                "broker.execution_engine.get_market_local_dt",
                return_value=datetime(2026, 8, 20, tzinfo=timezone.utc),
            ):
                account = engine.get_account()

        self.assertTrue(account["daily_realized_pnl_available"])
        self.assertEqual(account["daily_realized_pnl_date"], "2026-08-20")
        self.assertEqual(account["daily_realized_pnl_krw"], -12_000)
        self.assertEqual(account["realized_pnl_krw"], -12_000)
        self.assertEqual(account["daily_realized_trades"][0]["code"], "001450")
        client.get_domestic_period_trade_profit.assert_called_once_with("2026-08-20")

    def test_get_account_fails_closed_when_realized_pnl_lookup_fails(self) -> None:
        client = Mock()
        client.get_balance.return_value = {
            "mode": "real",
            "equity_krw": 3_600_000,
        }
        client.get_domestic_period_trade_profit.side_effect = RuntimeError("profit lookup failed")
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LiveBrokerExecutionEngine(
                kis_client=client,
                quote_provider=Mock(),
                fx_provider=Mock(),
                config=EngineConfig(state_path=Path(tmpdir) / "live.json"),
            )

            account = engine.get_account()

        self.assertFalse(account["ok"])
        self.assertEqual(account["mode"], "live")
        self.assertIn("profit lookup failed", account["error"])

    def test_get_account_propagates_ledger_capacity_error(self) -> None:
        client = Mock()
        error = KISLedgerCapacityError("EGW00215: 원장 처리량 초과")
        client.get_balance.side_effect = error
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LiveBrokerExecutionEngine(
                kis_client=client,
                quote_provider=Mock(),
                fx_provider=Mock(),
                config=EngineConfig(state_path=Path(tmpdir) / "live.json"),
            )

            with self.assertRaises(KISLedgerCapacityError) as raised:
                engine.get_account()

        self.assertIs(raised.exception, error)
        client.get_balance.assert_called_once_with()

    def test_place_order_propagates_ledger_capacity_error(self) -> None:
        client = Mock()
        client.get_sellable_quantity.return_value = {
            "sellable_quantity": 1,
            "balance_quantity": 1,
        }
        error = KISLedgerCapacityError("EGW00215: 원장 처리량 초과")
        client.place_cash_order.side_effect = error
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LiveBrokerExecutionEngine(
                kis_client=client,
                quote_provider=Mock(),
                fx_provider=Mock(),
                config=EngineConfig(state_path=Path(tmpdir) / "live.json"),
            )
            with (
                patch(
                    "broker.execution_engine._domestic_after_hours_order_division",
                    return_value="",
                ),
                self.assertRaises(KISLedgerCapacityError) as raised,
            ):
                engine.place_order(
                    side="sell",
                    code="006340",
                    market="KOSPI",
                    quantity=1,
                )

        self.assertIs(raised.exception, error)
        client.place_cash_order.assert_called_once()

    def test_place_order_propagates_request_audit_error(self) -> None:
        client = Mock()
        client.get_sellable_quantity.return_value = {
            "sellable_quantity": 1,
            "balance_quantity": 1,
        }
        client.place_cash_order.side_effect = KISRequestAuditError(
            "KIS 요청 감사 로그 저장 실패; 브로커 처리 결과 확인 필요"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LiveBrokerExecutionEngine(
                kis_client=client,
                quote_provider=Mock(),
                fx_provider=Mock(),
                config=EngineConfig(state_path=Path(tmpdir) / "live.json"),
            )
            with (
                patch(
                    "broker.execution_engine._domestic_after_hours_order_division",
                    return_value="",
                ),
                self.assertRaisesRegex(
                    KISRequestAuditError,
                    "브로커 처리 결과 확인 필요",
                ),
            ):
                engine.place_order(
                    side="sell",
                    code="006340",
                    market="KOSPI",
                    quantity=1,
                )

        client.place_cash_order.assert_called_once()

    def test_sell_is_capped_to_broker_sellable_quantity(self) -> None:
        client = Mock()
        client.get_sellable_quantity.return_value = {
            "sellable_quantity": 3,
            "balance_quantity": 5,
        }
        client.place_cash_order.return_value = {
            "order_no": "1001",
            "raw": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LiveBrokerExecutionEngine(
                kis_client=client,
                quote_provider=Mock(),
                fx_provider=Mock(),
                config=EngineConfig(state_path=Path(tmpdir) / "live.json"),
            )
            with patch(
                "broker.execution_engine._domestic_after_hours_order_division",
                return_value="",
            ):
                result = engine.place_order(
                    side="sell",
                    code="006340",
                    market="KOSPI",
                    quantity=5,
                )

        self.assertTrue(result["ok"])
        client.get_sellable_quantity.assert_called_once_with("006340")
        client.place_cash_order.assert_called_once_with(
            side="sell",
            code="006340",
            quantity=3,
            price=0,
            order_division="01",
        )
        self.assertEqual(result["event"]["requested_quantity"], 5)
        self.assertEqual(result["event"]["adjusted_quantity"], 3)
        self.assertEqual(result["event"]["sellable_amount"]["sellable_quantity"], 3)

    def test_sell_is_blocked_when_broker_sellable_quantity_is_zero(self) -> None:
        client = Mock()
        client.get_sellable_quantity.return_value = {
            "sellable_quantity": 0,
            "balance_quantity": 1,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = LiveBrokerExecutionEngine(
                kis_client=client,
                quote_provider=Mock(),
                fx_provider=Mock(),
                config=EngineConfig(state_path=Path(tmpdir) / "live.json"),
            )
            with patch(
                "broker.execution_engine._domestic_after_hours_order_division",
                return_value="",
            ):
                result = engine.place_order(
                    side="sell",
                    code="006340",
                    market="KOSPI",
                    quantity=1,
                )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "domestic_sellable_quantity_zero")
        client.place_cash_order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
