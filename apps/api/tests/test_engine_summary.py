from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from routes.engine import handle_engine_status, handle_engine_summary


class EngineSummaryTests(unittest.TestCase):
    def test_uses_hydrated_runtime_status_for_today_pnl(self) -> None:
        cached_status = (200, {
            "ok": True,
            "execution_mode": "paper",
            "state": {
                "running": True,
                "today_realized_pnl": 5984.76,
                "current_equity": 5_187_051.62,
            },
            "account": {
                "mode": "paper",
                "equity_krw": 5_187_051.62,
                "cash_krw": 5_187_051.62,
                "positions": [],
            },
        })
        with (
            patch("routes.engine.handle_cached_runtime_engine_status", return_value=cached_status) as status_handler,
            patch("routes.engine.list_strategy_scans", return_value=[]),
            patch("routes.engine._context_snapshot", return_value=("neutral", "normal")),
            patch("routes.engine.get_mode_status", return_value={"current_mode": "paper"}),
        ):
            status, payload = handle_engine_summary()

        self.assertEqual(status, 200)
        status_handler.assert_called_once_with()
        self.assertEqual(payload["execution"]["state"]["today_realized_pnl"], 5984.76)
        self.assertEqual(payload["execution"]["account"]["equity_krw"], 5_187_051.62)

    def test_summary_preserves_live_account_health_and_exposes_error_incident(self) -> None:
        cached_status = (200, {
            "ok": True,
            "execution_mode": "live",
            "account_available": False,
            "account_error": "runtime_account_unavailable: EGW00215",
            "state": {
                "engine_state": "error",
                "running": False,
                "last_error": "runtime_account_unavailable: EGW00215",
                "last_error_at": "2026-08-07T05:25:58+00:00",
            },
            "account": {},
        })
        with (
            patch("routes.engine.handle_cached_runtime_engine_status", return_value=cached_status),
            patch("routes.engine.list_strategy_scans", return_value=[]),
            patch("routes.engine._context_snapshot", return_value=("neutral", "normal")),
            patch("routes.engine.get_mode_status", return_value={"current_mode": "live_ready"}),
        ):
            status, payload = handle_engine_summary()

        execution = payload["execution"]
        incident = execution["state"]["incident_alert"]
        self.assertEqual(status, 200)
        self.assertFalse(execution["account_available"])
        self.assertEqual(execution["account_error"], "runtime_account_unavailable: EGW00215")
        self.assertTrue(incident["active"])
        self.assertEqual(incident["code"], "live_engine_error")
        self.assertEqual(incident["severity"], "critical")
        self.assertEqual(incident["occurred_at"], "2026-08-07T05:25:58+00:00")

    def test_summary_exposes_deferred_live_account_sync_as_warning(self) -> None:
        account_warning = "runtime_account_unavailable: EGW00215"
        cached_status = (200, {
            "ok": True,
            "execution_mode": "live",
            "account_available": True,
            "account_fresh": False,
            "account_error": "",
            "account_warning": account_warning,
            "state": {
                "engine_state": "running",
                "running": True,
                "account_sync_deferred": True,
                "last_account_sync_error": account_warning,
                "last_account_sync_error_at": "2026-08-14T03:46:25+00:00",
                "last_account_sync_cycle_id": "cycle-20260814-124625-e968ce94",
                "last_account_sync_cycle_type": "full",
            },
            "account": {
                "mode": "real",
                "equity_krw": 3_710_127,
                "cash_krw": 3_255_127,
                "positions": [],
            },
        })
        with (
            patch("routes.engine.handle_cached_runtime_engine_status", return_value=cached_status),
            patch("routes.engine.list_strategy_scans", return_value=[]),
            patch("routes.engine._context_snapshot", return_value=("neutral", "normal")),
            patch("routes.engine.get_mode_status", return_value={"current_mode": "live_ready"}),
        ):
            status, payload = handle_engine_summary()

        execution = payload["execution"]
        incident = execution["state"]["incident_alert"]
        self.assertEqual(status, 200)
        self.assertFalse(execution["account_fresh"])
        self.assertEqual(execution["account_warning"], account_warning)
        self.assertTrue(incident["active"])
        self.assertEqual(incident["code"], "live_account_sync_deferred")
        self.assertEqual(incident["severity"], "warning")
        self.assertNotEqual(incident["severity"], "critical")
        self.assertEqual(incident["detail"], account_warning)
        self.assertEqual(incident["occurred_at"], "2026-08-14T03:46:25+00:00")

    def test_full_status_uses_cached_contract_and_does_not_alert_manual_stop(self) -> None:
        cached_status = (200, {
            "ok": True,
            "execution_mode": "live",
            "account_available": True,
            "account_error": "",
            "state": {
                "engine_state": "stopped",
                "running": False,
                "stopped_at": "2026-08-12T01:00:00+00:00",
            },
            "account": {"mode": "real", "positions": []},
        })
        with (
            patch("routes.engine.handle_cached_runtime_engine_status", return_value=cached_status) as status_handler,
            patch("routes.engine.list_strategy_scans", return_value=[]),
            patch("routes.engine._context_snapshot", return_value=("neutral", "normal")),
            patch("routes.engine.get_mode_status", return_value={"current_mode": "live_ready"}),
            patch("routes.engine.summarize_registry", return_value={}),
        ):
            status, payload = handle_engine_status()

        self.assertEqual(status, 200)
        status_handler.assert_called_once_with()
        self.assertTrue(payload["execution"]["account_available"])
        self.assertNotIn("incident_alert", payload["execution"]["state"])

    def test_stopped_engine_does_not_claim_deferred_monitor_is_running(self) -> None:
        cached_status = (200, {
            "ok": True,
            "execution_mode": "live",
            "account_available": True,
            "account_fresh": False,
            "account_warning": "EGW00215: ledger busy",
            "state": {
                "engine_state": "stopped",
                "running": False,
                "account_sync_deferred": True,
                "last_account_sync_error": "EGW00215: ledger busy",
            },
            "account": {"mode": "real", "positions": []},
        })
        with (
            patch("routes.engine.handle_cached_runtime_engine_status", return_value=cached_status),
            patch("routes.engine.list_strategy_scans", return_value=[]),
            patch("routes.engine._context_snapshot", return_value=("neutral", "normal")),
            patch("routes.engine.get_mode_status", return_value={"current_mode": "live_ready"}),
            patch("routes.engine.summarize_registry", return_value={}),
        ):
            status, payload = handle_engine_status()

        self.assertEqual(status, 200)
        self.assertFalse(payload["execution"]["account_fresh"])
        self.assertNotIn("incident_alert", payload["execution"]["state"])


if __name__ == "__main__":
    unittest.main()
