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
from broker.kis_client import KISLedgerCapacityError


class ExecutionStatusTests(unittest.TestCase):
    def test_ledger_capacity_defers_cycle_without_stopping_engine(self) -> None:
        class StopOnWaitEvent:
            def __init__(self) -> None:
                self.stopped = False

            def is_set(self) -> bool:
                return self.stopped

            def set(self) -> None:
                self.stopped = True

            def wait(self, _timeout: float) -> bool:
                self.stopped = True
                return True

        error = execution_service.RuntimeAccountSyncDeferredError(
            "EGW00215: 원장에서 허용 가능한 초당 거래건수를 초과하였습니다."
        )
        notifier = Mock()
        append_cycle = Mock()
        state = {
            "engine_state": "running",
            "running": True,
            "account_sync_deferred": False,
            "consecutive_account_sync_deferrals": 0,
            "last_error": "",
            "last_error_at": "",
            "current_config": {
                "markets": ["KOSPI"],
                "interval_seconds": 300,
            },
        }

        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_auto_trader_cycle_lock", threading.Lock()),
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(
                execution_service,
                "_new_auto_trader_cycle_id",
                return_value="cycle-ledger-deferred",
            ),
            patch.object(
                execution_service,
                "_now_iso",
                side_effect=[
                    "2026-08-14T03:46:24+00:00",
                    "2026-08-14T03:46:25+00:00",
                ],
            ),
            patch.object(execution_service, "_run_auto_trader_cycle", side_effect=error),
            patch.object(execution_service, "get_notification_service", return_value=notifier),
            patch.object(execution_service, "append_engine_cycle", append_cycle),
        ):
            stop_event = StopOnWaitEvent()
            execution_service._auto_trader_loop(stop_event)  # type: ignore[arg-type]

        self.assertEqual(state["engine_state"], "running")
        self.assertTrue(state["running"])
        self.assertTrue(state["account_sync_deferred"])
        self.assertEqual(state["consecutive_account_sync_deferrals"], 1)
        self.assertEqual(state["latest_cycle_id"], "cycle-ledger-deferred")
        self.assertEqual(state["last_error"], "")
        notifier.notify_engine_error.assert_not_called()
        notifier.notify_account_sync_deferred.assert_called_once_with(
            error=str(error),
            cycle_id="cycle-ledger-deferred",
            cycle_type="full",
            occurred_at="2026-08-14T03:46:25+00:00",
        )
        append_cycle.assert_called_once_with({
            "ok": False,
            "status": "deferred",
            "cycle_type": "full",
            "cycle_id": "cycle-ledger-deferred",
            "started_at": "2026-08-14T03:46:24+00:00",
            "finished_at": "2026-08-14T03:46:25+00:00",
            "reason_code": "kis_ledger_capacity",
            "orders_blocked": True,
            "engine_continues": True,
            "error": str(error),
        })

    def test_repeated_ledger_deferrals_notify_once(self) -> None:
        notifier = Mock()
        state = {
            "engine_state": "running",
            "running": True,
            "account_sync_deferred": False,
            "consecutive_account_sync_deferrals": 0,
        }
        error = execution_service.RuntimeAccountSyncDeferredError("EGW00215: ledger busy")
        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(execution_service, "append_engine_cycle"),
            patch.object(execution_service, "get_notification_service", return_value=notifier),
        ):
            for index in (1, 2):
                execution_service._record_account_sync_deferral(
                    error=error,
                    cycle_id=f"cycle-{index}",
                    cycle_type="full",
                    started_at=f"start-{index}",
                    deferred_at=f"end-{index}",
                )

        self.assertTrue(state["account_sync_deferred"])
        self.assertEqual(state["consecutive_account_sync_deferrals"], 2)
        self.assertEqual(state["latest_cycle_id"], "cycle-2")
        notifier.notify_account_sync_deferred.assert_called_once()

    def test_ledger_deferral_does_not_revive_manually_stopped_engine(self) -> None:
        notifier = Mock()
        append_cycle = Mock()
        state = {
            "engine_state": "stopped",
            "running": False,
            "account_sync_deferred": False,
            "consecutive_account_sync_deferrals": 0,
        }
        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(execution_service, "append_engine_cycle", append_cycle),
            patch.object(execution_service, "get_notification_service", return_value=notifier),
        ):
            execution_service._record_account_sync_deferral(
                error=execution_service.RuntimeAccountSyncDeferredError("EGW00215: ledger busy"),
                cycle_id="cycle-after-stop",
                cycle_type="full",
                started_at="start",
                deferred_at="end",
            )

        self.assertEqual(state["engine_state"], "stopped")
        self.assertFalse(state["running"])
        self.assertFalse(state["account_sync_deferred"])
        notifier.notify_account_sync_deferred.assert_not_called()
        self.assertFalse(append_cycle.call_args.args[0]["engine_continues"])

    def test_third_consecutive_account_sync_deferral_stops_engine(self) -> None:
        notifier = Mock()
        append_cycle = Mock()
        state = {
            "engine_state": "running",
            "running": True,
            "account_sync_deferred": False,
            "consecutive_account_sync_deferrals": 0,
            "last_error": "",
            "last_error_at": "",
        }
        error = execution_service.RuntimeAccountSyncDeferredError("EGW00215: ledger busy")
        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(execution_service, "append_engine_cycle", append_cycle),
            patch.object(execution_service, "get_notification_service", return_value=notifier),
        ):
            results = [
                execution_service._record_account_sync_deferral(
                    error=error,
                    cycle_id=f"cycle-{index}",
                    cycle_type="full",
                    started_at=f"start-{index}",
                    deferred_at=f"end-{index}",
                )
                for index in (1, 2, 3)
            ]

        self.assertEqual(results, [True, True, False])
        self.assertEqual(state["engine_state"], "error")
        self.assertFalse(state["running"])
        self.assertEqual(state["consecutive_account_sync_deferrals"], 3)
        self.assertEqual(
            state["last_error"],
            "runtime_account_sync_deferred_limit: EGW00215: ledger busy",
        )
        notifier.notify_account_sync_deferred.assert_called_once()
        notifier.notify_engine_error.assert_called_once_with(
            error="runtime_account_sync_deferred_limit: EGW00215: ledger busy",
            cycle_id="cycle-3",
        )
        self.assertEqual(append_cycle.call_args.args[0]["status"], "error")
        self.assertFalse(append_cycle.call_args.args[0]["engine_continues"])

    def test_successful_fresh_account_sync_clears_deferral_state(self) -> None:
        class StopOnWaitEvent:
            def __init__(self) -> None:
                self.stopped = False

            def is_set(self) -> bool:
                return self.stopped

            def set(self) -> None:
                self.stopped = True

            def wait(self, _timeout: float) -> bool:
                self.stopped = True
                return True

        state = {
            "engine_state": "running",
            "running": True,
            "account_sync_deferred": True,
            "consecutive_account_sync_deferrals": 2,
            "last_error": "",
            "last_error_at": "",
            "current_config": {"markets": ["KOSPI"], "interval_seconds": 300},
        }
        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_auto_trader_cycle_lock", threading.Lock()),
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(execution_service, "_new_auto_trader_cycle_id", return_value="cycle-recovered"),
            patch.object(
                execution_service,
                "_now_iso",
                side_effect=["2026-08-14T04:10:00+00:00", "2026-08-14T04:10:01+00:00"],
            ),
            patch.object(
                execution_service,
                "_run_auto_trader_cycle",
                return_value={
                    "ok": True,
                    "cycle_id": "cycle-recovered",
                    "account_sync_performed": True,
                },
            ),
        ):
            execution_service._auto_trader_loop(StopOnWaitEvent())  # type: ignore[arg-type]

        self.assertFalse(state["account_sync_deferred"])
        self.assertEqual(state["consecutive_account_sync_deferrals"], 0)
        self.assertEqual(state["last_success_at"], "2026-08-14T04:10:01+00:00")
        self.assertEqual(state["last_account_sync_at"], "2026-08-14T04:10:01+00:00")

    def test_non_initial_ledger_capacity_error_still_stops_engine(self) -> None:
        error = KISLedgerCapacityError("EGW00215: ledger busy")
        notifier = Mock()
        state = {
            "engine_state": "running",
            "running": True,
            "account_sync_deferred": False,
            "current_config": {"markets": ["KOSPI"], "interval_seconds": 300},
        }
        with (
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_auto_trader_cycle_lock", threading.Lock()),
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_persist_auto_trader_state_locked"),
            patch.object(execution_service, "_new_auto_trader_cycle_id", return_value="cycle-order-stage"),
            patch.object(
                execution_service,
                "_now_iso",
                side_effect=["2026-08-14T04:00:00+00:00", "2026-08-14T04:00:01+00:00"],
            ),
            patch.object(execution_service, "_run_auto_trader_cycle", side_effect=error),
            patch.object(execution_service, "get_notification_service", return_value=notifier),
            patch.object(execution_service, "append_engine_cycle"),
        ):
            stop_event = threading.Event()
            execution_service._auto_trader_loop(stop_event)

        self.assertTrue(stop_event.is_set())
        self.assertEqual(state["engine_state"], "error")
        self.assertFalse(state["running"])
        notifier.notify_account_sync_deferred.assert_not_called()
        notifier.notify_engine_error.assert_called_once_with(
            error="EGW00215: ledger busy",
            cycle_id="cycle-order-stage",
        )

    def test_initial_live_balance_ledger_capacity_is_wrapped_for_deferral(self) -> None:
        engine = Mock()
        engine.get_account.side_effect = KISLedgerCapacityError("EGW00215: ledger busy")
        with (
            patch.object(execution_service, "_runtime_engine", return_value=engine),
            patch.object(execution_service, "_current_execution_mode", return_value="live"),
            patch.object(execution_service, "is_market_open", return_value=True),
            patch.object(execution_service, "get_notification_service", return_value=Mock()),
        ):
            with self.assertRaisesRegex(
                execution_service.RuntimeAccountSyncDeferredError,
                "EGW00215",
            ):
                execution_service._run_auto_trader_cycle({"markets": ["KOSPI"]})

        engine.get_account.assert_called_once_with(refresh_quotes=True)

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
            patch.object(execution_service, "_current_execution_mode", return_value="live"),
            patch.object(execution_service, "is_market_open", return_value=True),
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

    def test_status_marks_cached_account_stale_during_sync_deferral(self) -> None:
        engine = Mock()
        cached_account = {
            "mode": "real",
            "equity_krw": 3_710_127,
            "cash_krw": 3_255_127,
            "positions": [],
        }
        persisted_state = {
            "engine_state": "running",
            "running": True,
            "account_sync_deferred": True,
            "last_account_sync_error": "EGW00215: ledger busy",
            "last_account_sync_error_at": "2026-08-14T03:46:25+00:00",
            "consecutive_account_sync_deferrals": 2,
            "current_config": {"markets": ["KOSPI"]},
        }
        with (
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_ensure_auto_trader_thread_running"),
            patch.object(execution_service, "_auto_trader_state", persisted_state),
            patch.object(execution_service, "_current_execution_mode", return_value="live"),
            patch.object(execution_service, "_read_cached_live_runtime_account", return_value=cached_account),
            patch.object(execution_service, "_runtime_engine", return_value=engine),
        ):
            status, payload = execution_service.handle_runtime_engine_status()

        self.assertEqual(status, 200)
        self.assertTrue(payload["account_available"])
        self.assertFalse(payload["account_fresh"])
        self.assertEqual(payload["account_warning"], "EGW00215: ledger busy")
        self.assertTrue(payload["state"]["account_sync_deferred"])
        engine.get_account.assert_not_called()

    def test_status_marks_account_fresh_after_manual_recovery_without_restarting_engine(self) -> None:
        engine = Mock()
        cached_account = {
            "mode": "real",
            "equity_krw": 3_703_817,
            "cash_krw": 2_953_917,
            "positions": [],
        }
        persisted_state = {
            "engine_state": "error",
            "running": False,
            "last_error": "runtime_account_sync_deferred_limit: EGW00215: ledger busy",
            "last_error_at": "2026-08-18T00:31:04+00:00",
            "last_account_recovered_at": "2026-08-18T01:42:54+00:00",
            "account_sync_deferred": False,
            "consecutive_account_sync_deferrals": 0,
            "current_config": {"markets": ["KOSPI"]},
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
        self.assertTrue(payload["account_available"])
        self.assertTrue(payload["account_fresh"])
        self.assertEqual(payload["account_error"], "")
        self.assertEqual(payload["state"]["engine_state"], "error")
        self.assertEqual(
            payload["state"]["last_error"],
            "runtime_account_sync_deferred_limit: EGW00215: ledger busy",
        )
        engine.get_account.assert_not_called()

    def test_manual_live_account_refresh_persists_fills_and_records_recovery(self) -> None:
        engine = Mock()
        raw_account = {"mode": "real", "positions": []}
        normalized_account = {
            "mode": "real",
            "equity_krw": 3_703_817,
            "cash_krw": 2_953_917,
            "positions": [],
        }
        engine.get_account.return_value = raw_account
        state = {
            "engine_state": "error",
            "running": False,
            "account_sync_deferred": True,
            "consecutive_account_sync_deferrals": 3,
            "last_account_sync_error": "EGW00215: ledger busy",
            "last_account_sync_error_at": "2026-08-18T01:41:54+00:00",
        }
        normalize_account = Mock(return_value=normalized_account)
        persist_account = Mock()
        persist_state = Mock()
        with (
            patch.object(execution_service, "_runtime_engine", return_value=engine),
            patch.object(execution_service, "_current_execution_mode", return_value="live"),
            patch.object(execution_service, "_normalize_runtime_account", normalize_account),
            patch.object(execution_service, "_persist_live_runtime_account", persist_account),
            patch.object(execution_service, "_hydrate_auto_trader_state"),
            patch.object(execution_service, "_auto_trader_state", state),
            patch.object(execution_service, "_persist_auto_trader_state_locked", persist_state),
            patch.object(execution_service, "_now_iso", return_value="2026-08-18T01:42:54+00:00"),
        ):
            status, payload = execution_service.handle_runtime_account(refresh_quotes=True)

        self.assertEqual(status, 200)
        self.assertEqual(payload, normalized_account)
        engine.get_account.assert_called_once_with(refresh_quotes=True)
        normalize_account.assert_called_once_with(
            raw_account,
            persist_live_reconciled_fills=True,
            notify_live_fills=True,
        )
        persist_account.assert_called_once_with(normalized_account)
        self.assertFalse(state["account_sync_deferred"])
        self.assertEqual(state["consecutive_account_sync_deferrals"], 0)
        self.assertEqual(state["last_account_sync_error"], "")
        self.assertEqual(state["last_account_sync_error_at"], "")
        self.assertEqual(state["last_account_sync_at"], "2026-08-18T01:42:54+00:00")
        self.assertEqual(state["last_account_recovered_at"], "2026-08-18T01:42:54+00:00")
        persist_state.assert_called_once_with()

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
            patch.object(execution_service, "_current_execution_mode", return_value="live"),
            patch.object(execution_service, "is_market_open", return_value=True),
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
