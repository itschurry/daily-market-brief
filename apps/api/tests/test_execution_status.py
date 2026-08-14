from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import services.execution_service as execution_service
import routes.trading as trading_routes


class ExecutionStatusTests(unittest.TestCase):
    def test_initial_account_failure_records_the_attempted_cycle_id(self) -> None:
        engine = Mock()
        engine.get_account.return_value = {
            "ok": False,
            "mode": "real",
            "error": "EGW00215",
        }
        notifier = Mock()
        append_cycle = Mock()
        state = {
            "engine_state": "running",
            "running": True,
            "current_config": {
                "markets": ["KOSPI"],
                "interval_seconds": 300,
            },
        }

        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(execution_service, "_runtime_engine", return_value=engine),
            patch.object(execution_service, "_new_auto_trader_cycle_id", return_value="cycle-failed-account"),
            patch.object(execution_service, "_now_iso", side_effect=[
                "2026-08-14T00:02:27+00:00",
                "2026-08-14T00:02:28+00:00",
            ]),
            patch.object(execution_service, "get_notification_service", return_value=notifier),
            patch.object(execution_service, "append_engine_cycle", append_cycle),
        ):
            stop_event = threading.Event()
            execution_service._auto_trader_loop(stop_event)

        self.assertTrue(stop_event.is_set())
        self.assertEqual(state["engine_state"], "error")
        self.assertEqual(state["latest_cycle_id"], "cycle-failed-account")
        notifier.notify_engine_error.assert_called_once_with(
            error="runtime_account_unavailable: EGW00215",
            cycle_id="cycle-failed-account",
        )
        append_cycle.assert_called_once_with({
            "ok": False,
            "cycle_type": "full",
            "cycle_id": "cycle-failed-account",
            "started_at": "2026-08-14T00:02:27+00:00",
            "finished_at": "2026-08-14T00:02:28+00:00",
            "error": "runtime_account_unavailable: EGW00215",
        })

    def test_exit_account_failure_records_the_attempted_exit_cycle_id(self) -> None:
        class ImmediateEvent:
            def __init__(self) -> None:
                self.stopped = False

            def is_set(self) -> bool:
                return self.stopped

            def set(self) -> None:
                self.stopped = True

            def wait(self, _timeout: float) -> bool:
                return False

        notifier = Mock()
        append_cycle = Mock()
        state = {
            "engine_state": "running",
            "running": True,
            "current_config": {
                "markets": ["KOSPI"],
                "interval_seconds": 300,
                "exit_monitor_interval_seconds": 60,
            },
        }

        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(
                execution_service,
                "_new_auto_trader_cycle_id",
                side_effect=["cycle-full-ok", "cycle-exit-failed"],
            ),
            patch.object(execution_service, "_now_iso", return_value="2026-08-14T00:02:28+00:00"),
            patch.object(
                execution_service,
                "_run_auto_trader_cycle",
                return_value={"cycle_id": "cycle-full-ok"},
            ),
            patch.object(
                execution_service,
                "_load_exit_monitor_account",
                side_effect=execution_service.RuntimeAccountUnavailableError(
                    "runtime_account_unavailable: EGW00215"
                ),
            ),
            patch.object(execution_service, "get_notification_service", return_value=notifier),
            patch.object(execution_service, "append_engine_cycle", append_cycle),
        ):
            stop_event = ImmediateEvent()
            execution_service._auto_trader_loop(stop_event)  # type: ignore[arg-type]

        self.assertTrue(stop_event.is_set())
        self.assertEqual(state["engine_state"], "error")
        self.assertEqual(state["latest_cycle_id"], "cycle-exit-failed")
        notifier.notify_engine_error.assert_called_once_with(
            error="runtime_account_unavailable: EGW00215",
            cycle_id="cycle-exit-failed",
        )
        append_cycle.assert_called_once_with({
            "ok": False,
            "cycle_type": "exit_monitor",
            "cycle_id": "cycle-exit-failed",
            "started_at": "2026-08-14T00:02:28+00:00",
            "finished_at": "2026-08-14T00:02:28+00:00",
            "error": "runtime_account_unavailable: EGW00215",
        })

    def test_status_exposes_account_error_without_losing_persisted_state(self) -> None:
        engine = Mock()
        cached_account = {
            "mode": "real",
            "equity_krw": 3_755_370,
            "cash_krw": 3_755_370,
            "positions": [],
        }
        persisted_state = {
            "engine_state": "error",
            "running": False,
            "last_error": "runtime_account_unavailable: EGW00215",
            "today_order_counts": {"buy": 1, "sell": 0, "failed": 0},
            "last_summary": {
                "cycle_id": "cycle-1",
                "executed_buy_count": 1,
                "executed_sell_count": 0,
                "skipped": [{"reason": "blocked"}],
                "account": {"raw": "must_not_leak"},
            },
            "current_config": {
                "interval_seconds": 120,
                "markets": ["KOSPI"],
            },
        }

        with (
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_auto_trader_state", persisted_state),
            patch.object(execution_service, "_current_execution_mode", return_value="live"),
            patch.object(execution_service, "_read_cached_live_runtime_account", return_value=cached_account),
            patch.object(execution_service, "_runtime_engine", return_value=engine),
        ):
            status, payload = execution_service.handle_runtime_engine_status()

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["account_available"])
        self.assertEqual(payload["account"]["equity_krw"], 3_755_370)
        self.assertEqual(payload["account_error"], "runtime_account_unavailable: EGW00215")
        self.assertEqual(payload["state"]["engine_state"], "error")
        self.assertEqual(payload["state"]["last_error"], "runtime_account_unavailable: EGW00215")
        self.assertEqual(payload["state"]["current_config"]["interval_seconds"], 120)
        self.assertEqual(payload["state"]["config"], payload["state"]["current_config"])
        engine.get_account.assert_not_called()

    def test_service_live_status_marks_missing_cache_without_broker_call(self) -> None:
        engine = Mock()
        with (
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(
                execution_service,
                "_auto_trader_state",
                {"engine_state": "stopped", "running": False},
            ),
            patch.object(execution_service, "_current_execution_mode", return_value="live"),
            patch.object(execution_service, "_read_cached_live_runtime_account", return_value={}),
            patch.object(execution_service, "_runtime_engine", return_value=engine),
        ):
            status, payload = execution_service.handle_runtime_engine_status()

        self.assertEqual(status, 200)
        self.assertFalse(payload["account_available"])
        self.assertEqual(payload["account_error"], "live_account_state_unavailable")
        engine.get_account.assert_not_called()

    def test_runtime_status_route_preserves_degraded_account_contract(self) -> None:
        persisted_state = {
            "engine_state": "error",
            "running": False,
            "last_error": "runtime_account_unavailable: EGW00215",
            "today_order_counts": {"buy": 1, "sell": 0, "failed": 0},
            "last_summary": {
                "cycle_id": "cycle-1",
                "executed_buy_count": 1,
                "executed_sell_count": 0,
                "skipped": [{"reason": "blocked"}],
                "account": {"raw": "must_not_leak"},
            },
            "current_config": {
                "interval_seconds": 120,
                "markets": ["KOSPI"],
            },
            "config": {
                "interval_seconds": 120,
                "markets": ["KOSPI"],
            },
        }
        cached_account = {
            "mode": "real",
            "equity_krw": 3_755_370,
            "positions": [],
        }

        service = Mock()
        service.runtime_engine_status.return_value = (200, {
            "ok": True,
            "execution_mode": "live",
            "state": persisted_state,
            "account": cached_account,
            "account_available": False,
            "account_error": "runtime_account_unavailable: EGW00215",
        })
        with patch.object(trading_routes, "get_execution_service", return_value=service):
            status, payload = trading_routes.handle_runtime_engine_status()

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["account_available"])
        self.assertEqual(payload["account_error"], "runtime_account_unavailable: EGW00215")
        self.assertEqual(payload["account"]["equity_krw"], 3_755_370)
        self.assertEqual(payload["state"]["engine_state"], "error")
        self.assertEqual(payload["state"]["current_config"]["interval_seconds"], 120)
        self.assertEqual(payload["state"]["today_order_counts"]["buy"], 1)
        self.assertEqual(payload["state"]["last_summary"]["executed_buy_count"], 1)
        self.assertEqual(payload["state"]["last_summary"]["skipped_count"], 1)
        self.assertNotIn("account", payload["state"]["last_summary"])
        service.runtime_engine_status.assert_called_once_with()

    def test_trading_cycle_still_raises_on_account_error(self) -> None:
        engine = Mock()
        engine.get_account.return_value = {
            "ok": False,
            "mode": "real",
            "error": "EGW00215",
        }

        with (
            patch.object(execution_service, "_runtime_engine", return_value=engine),
            patch.object(execution_service, "get_notification_service", return_value=Mock()),
        ):
            with self.assertRaisesRegex(RuntimeError, "runtime_account_unavailable: EGW00215"):
                execution_service._run_auto_trader_cycle({"markets": ["KOSPI"]})

    def test_runtime_status_route_marks_missing_live_cache_unavailable(self) -> None:
        service = Mock()
        service.runtime_engine_status.return_value = (200, {
            "ok": True,
            "execution_mode": "live",
            "state": {"engine_state": "stopped", "running": False},
            "account": {},
            "account_available": False,
            "account_error": "live_account_state_unavailable",
        })
        with patch.object(trading_routes, "get_execution_service", return_value=service):
            status, payload = trading_routes.handle_runtime_engine_status()

        self.assertEqual(status, 200)
        self.assertFalse(payload["account_available"])
        self.assertEqual(payload["account_error"], "live_account_state_unavailable")


if __name__ == "__main__":
    unittest.main()
