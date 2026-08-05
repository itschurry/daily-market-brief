from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from services.execution_service import (
    _allows_rotation_candidate,
    _candidate_leadership_rank,
    _candidate_unit_price_local,
    _candidate_execution_risk_plan,
    _buy_capacity_block_reason_from_orders,
    _default_auto_trader_config,
    _hydrate_live_runtime_account,
    _promote_operator_review_candidate_for_entry,
    _promote_priority_candidate_for_entry,
    _position_exit_reason_by_pnl,
    _refresh_trailing_profit_peak,
    _run_auto_trader_cycle,
    _select_rotation_plan,
    _should_run_exit_monitor,
    _should_attempt_rotation,
    _sync_primary_strategy_fields,
    _symbol_reentry_blocked,
)
from datetime import datetime, timedelta, timezone


def _buy_research_layer() -> dict:
    return {
        "rating": "overweight",
        "action": "buy",
        "technical_features": {
            "change_pct": 3.0,
            "close_vs_sma20": 1.03,
            "close_vs_sma60": 1.06,
            "volume_ratio": 1.25,
        },
    }


def _buy_agent_snapshot() -> dict:
    return {
        "agent_decision": {
            "decision": "agent_buy_watch",
            "rating": "overweight",
            "action": "buy_watch",
        },
    }


def _primary_buy_snapshot() -> dict:
    return {
        "agent_decision": {
            "decision": "agent_primary_buy",
            "rating": "overweight",
            "action": "buy",
        },
        "quant_decision": {
            "decision": "quant_entry",
            "order_ready": True,
        },
    }


class ExecutionRotationTests(unittest.TestCase):
    def test_explicit_conservative_live_limits_are_preserved(self) -> None:
        config = _sync_primary_strategy_fields({
            **_default_auto_trader_config(),
            "max_positions_per_market": 2,
            "risk_per_trade_pct": 0.5,
            "max_symbol_weight_pct": 20.0,
            "max_sector_weight_pct": 35.0,
            "max_market_exposure_pct": 40.0,
        })

        self.assertEqual(config["max_positions_per_market"], 2)
        self.assertEqual(config["market_profiles"]["KOSPI"]["max_positions"], 2)
        self.assertEqual(config["risk_per_trade_pct"], 0.5)
        self.assertEqual(config["max_symbol_weight_pct"], 20.0)
        self.assertEqual(config["max_sector_weight_pct"], 35.0)
        self.assertEqual(config["max_market_exposure_pct"], 40.0)

    def test_stale_rotation_config_is_normalized_to_safe_limits(self) -> None:
        config = _sync_primary_strategy_fields({
            **_default_auto_trader_config(),
            "rotation": {
                "enabled": False,
                "min_score_gap": 5.0,
                "daily_limit": 6,
                "min_holding_days": 0,
                "min_holding_minutes": 30,
            },
        })

        self.assertFalse(config["rotation"]["enabled"])
        self.assertEqual(config["rotation"]["min_score_gap"], 8.0)
        self.assertEqual(config["rotation"]["daily_limit"], 1)
        self.assertEqual(config["rotation"]["min_holding_days"], 2)
        self.assertEqual(config["rotation"]["min_holding_minutes"], 1440)

    def test_exit_monitor_interval_is_separate_and_capped_at_sixty_seconds(self) -> None:
        default_config = _default_auto_trader_config()
        self.assertEqual(default_config["exit_monitor_interval_seconds"], 60)

        config = _sync_primary_strategy_fields({
            **default_config,
            "interval_seconds": 300,
            "exit_monitor_interval_seconds": 90,
        })
        self.assertEqual(config["interval_seconds"], 300)
        self.assertEqual(config["exit_monitor_interval_seconds"], 60)

        config = _sync_primary_strategy_fields({
            **default_config,
            "interval_seconds": 45,
            "exit_monitor_interval_seconds": 60,
        })
        self.assertEqual(config["exit_monitor_interval_seconds"], 45)

    @patch("services.execution_service.is_market_open", return_value=True)
    @patch("services.execution_service._runtime_engine")
    def test_exit_monitor_runs_only_for_managed_positions(
        self,
        runtime_engine: Mock,
        _is_market_open: Mock,
    ) -> None:
        engine = runtime_engine.return_value
        engine.get_account.return_value = {
            "positions": [{
                "market": "KOSPI",
                "code": "005930",
                "entry_plan_price": 100000,
                "stop_loss_price": 94000,
                "take_profit_price": 112000,
            }],
        }
        self.assertTrue(_should_run_exit_monitor({"markets": ["KOSPI"]}))

        engine.get_account.return_value = {
            "positions": [{"market": "KOSPI", "code": "005930"}],
        }
        self.assertFalse(_should_run_exit_monitor({"markets": ["KOSPI"]}))

    def test_exit_monitor_cycle_skips_technicals_and_entry_scan(self) -> None:
        account = {
            "mode": "paper",
            "cash_krw": 4_500_000,
            "equity_krw": 5_000_000,
            "orders": [],
            "positions": [{
                "market": "KOSPI",
                "code": "005930",
                "quantity": 5,
                "entry_plan_price": 100000,
                "stop_loss_price": 94000,
                "take_profit_price": 112000,
                "avg_price_local": 100000,
                "last_price_local": 100000,
                "unrealized_pnl_pct": 0.0,
                "unrealized_pnl_krw": 0.0,
            }],
        }
        engine = Mock()
        engine.get_account.return_value = account

        with (
            patch("services.execution_service._runtime_engine", return_value=engine),
            patch(
                "services.execution_service._normalize_runtime_account",
                side_effect=lambda value, **_: value,
            ),
            patch("services.execution_service._runtime_order_attempts", return_value=[]),
            patch("services.execution_service.is_market_open", return_value=True),
            patch("services.execution_service._compute_technical_snapshot") as technicals,
            patch("services.execution_service.build_signal_book") as signal_book,
            patch("services.execution_service._persist_live_runtime_account"),
            patch("services.execution_service.append_signal_snapshots"),
            patch("services.execution_service.append_engine_cycle"),
            patch("services.execution_service.append_account_snapshot"),
            patch("services.execution_service._should_send_market_open_brief", return_value=(False, "")),
            patch("services.execution_service.get_notification_service", return_value=Mock()),
        ):
            summary = _run_auto_trader_cycle(
                _default_auto_trader_config(),
                entry_scan=False,
            )

        self.assertEqual(summary["cycle_type"], "exit_monitor")
        self.assertEqual(summary["executed_buy_count"], 0)
        technicals.assert_not_called()
        signal_book.assert_not_called()

    def test_exit_monitor_restores_live_risk_plan_before_sell_check(self) -> None:
        raw_account = {
            "mode": "real",
            "cash_krw": 3_100_000,
            "equity_krw": 3_750_000,
            "orders": [],
            "positions": [{
                "market": "KOSPI",
                "code": "073240",
                "name": "금호타이어",
                "quantity": 33,
                "avg_price_local": 7020,
                "last_price_local": 6660,
                "unrealized_pnl_pct": -5.12,
                "orderable_quantity": 33,
            }],
        }
        engine = Mock()
        engine.get_account.return_value = raw_account
        engine.place_order.return_value = {
            "ok": True,
            "event": {"quantity": 33, "filled_at": "2026-08-03T06:00:00+00:00"},
            "account": {"orders": []},
        }

        normalize_calls = 0

        def normalize(account: dict, **_: object) -> dict:
            nonlocal normalize_calls
            normalize_calls += 1
            normalized = {**account, "positions": [dict(item) for item in account["positions"]]}
            if normalize_calls >= 2:
                normalized["positions"][0].update({
                    "entry_plan_price": 7150,
                    "stop_loss_price": 6265,
                    "take_profit_price": 8100,
                })
            return normalized

        with (
            patch("services.execution_service._runtime_engine", return_value=engine),
            patch("services.execution_service._normalize_runtime_account", side_effect=normalize),
            patch("services.execution_service._runtime_order_attempts", return_value=[]),
            patch("services.execution_service.is_market_open", return_value=True),
            patch("services.execution_service._persist_live_runtime_account"),
            patch("services.execution_service._record_execution_order"),
            patch("services.execution_service.append_signal_snapshots"),
            patch("services.execution_service.append_engine_cycle"),
            patch("services.execution_service.append_account_snapshot"),
            patch("services.execution_service._should_send_market_open_brief", return_value=(False, "")),
            patch("services.execution_service.get_notification_service", return_value=Mock()),
        ):
            summary = _run_auto_trader_cycle(
                _default_auto_trader_config(),
                entry_scan=False,
            )

        self.assertGreaterEqual(normalize_calls, 3)
        self.assertEqual(summary["executed_sell_count"], 1)
        self.assertEqual(summary["executed_sells"][0]["reason"], "비상손절")
        engine.place_order.assert_called_once_with(
            side="sell",
            code="073240",
            market="KOSPI",
            quantity=33,
            order_type="market",
        )

    def test_live_account_restores_plan_from_matching_legacy_order_event(self) -> None:
        account = {
            "mode": "real",
            "account_product_code": "01",
            "positions": [{
                "market": "KOSPI",
                "code": "073240",
                "entry_ts": "2026-07-31T05:45:42+00:00",
                "stop_loss_price": None,
                "take_profit_price": None,
                "entry_plan_price": None,
            }],
        }
        legacy_live_order = {
            "success": True,
            "side": "buy",
            "market": "KOSPI",
            "code": "073240",
            "submitted_at": "2026-07-31T05:40:41+00:00",
            "order_id": "legacy-uuid-without-mode",
            "stop_loss_price": 6265,
            "take_profit_price": 8100,
            "entry_plan_price": 7150,
        }

        with (
            patch("services.execution_service.read_order_events", return_value=[legacy_live_order]),
            patch("services.execution_service.read_execution_events", return_value=[]),
            patch("services.execution_service._load_live_position_entries", return_value={
                "real:01": {"KOSPI:073240": "2026-07-31T05:45:42+00:00"},
            }),
            patch("services.execution_service._save_live_position_entries"),
        ):
            hydrated = _hydrate_live_runtime_account(account)

        position = hydrated["positions"][0]
        self.assertEqual(position["entry_plan_price"], 7150)
        self.assertEqual(position["stop_loss_price"], 6265)
        self.assertEqual(position["take_profit_price"], 8100)

    def test_symbol_reentry_is_blocked_for_three_days_after_sell(self) -> None:
        orders = [{
            "timestamp": "2026-07-13T01:00:00+00:00",
            "success": True,
            "market": "KOSPI",
            "code": "005930",
            "side": "sell",
        }]

        self.assertTrue(_symbol_reentry_blocked(
            orders,
            market="KOSPI",
            code="005930",
            min_reentry_days=3,
            today="2026-07-14",
        ))
        self.assertFalse(_symbol_reentry_blocked(
            orders,
            market="KOSPI",
            code="005930",
            min_reentry_days=3,
            today="2026-07-16",
        ))

    def test_symbol_reentry_ignores_failed_sell(self) -> None:
        orders = [{
            "timestamp": "2026-07-14T01:00:00+00:00",
            "success": False,
            "market": "KOSPI",
            "code": "005930",
            "side": "sell",
        }]

        self.assertFalse(_symbol_reentry_blocked(
            orders,
            market="KOSPI",
            code="005930",
            min_reentry_days=3,
            today="2026-07-14",
        ))

    def test_buy_capacity_block_reason_after_repeated_orderable_zero(self) -> None:
        orders = [
            {
                "timestamp": "2026-07-10T03:52:16+00:00",
                "success": False,
                "side": "buy",
                "failure_reason": "domestic_orderable_quantity_zero",
            },
            {
                "timestamp": "2026-07-10T03:53:16+00:00",
                "success": False,
                "side": "buy",
                "failure_reason": "domestic_orderable_quantity_zero",
            },
            {
                "timestamp": "2026-07-10T03:54:16+00:00",
                "success": False,
                "side": "buy",
                "failure_reason": "domestic_orderable_quantity_zero",
            },
        ]

        self.assertEqual(
            _buy_capacity_block_reason_from_orders(orders, "2026-07-10"),
            "domestic_orderable_quantity_zero",
        )

    def test_buy_capacity_block_reason_ignores_other_days_and_sells(self) -> None:
        orders = [
            {
                "timestamp": "2026-07-09T03:52:16+00:00",
                "success": False,
                "side": "buy",
                "failure_reason": "domestic_orderable_quantity_zero",
            },
            {
                "timestamp": "2026-07-10T03:53:16+00:00",
                "success": False,
                "side": "sell",
                "failure_reason": "domestic_orderable_quantity_zero",
            },
        ]

        self.assertEqual(_buy_capacity_block_reason_from_orders(orders, "2026-07-10"), "")

    def test_pnl_exit_uses_stop_loss_take_profit_and_trailing_profit(self) -> None:
        managed = {"entry_plan_price": 100000, "stop_loss_price": 94000, "take_profit_price": 112000}
        self.assertEqual(_position_exit_reason_by_pnl({"unrealized_pnl_pct": -5.0, **managed}, {}, "KOSPI"), "비상손절")
        self.assertIsNone(_position_exit_reason_by_pnl({"unrealized_pnl_pct": -4.99, **managed}, {}, "KOSPI"))
        self.assertEqual(_position_exit_reason_by_pnl({"unrealized_pnl_pct": 12.0, **managed}, {}, "KOSPI"), "익절")
        self.assertIsNone(_position_exit_reason_by_pnl({"unrealized_pnl_pct": 11.99, **managed}, {}, "KOSPI"))
        self.assertEqual(
            _position_exit_reason_by_pnl(
                {"last_price_local": 94000, "avg_price_local": 100000, **managed},
                {},
                "KOSPI",
            ),
            "손절",
        )
        self.assertEqual(
            _position_exit_reason_by_pnl(
                {"unrealized_pnl_pct": 0.1, "peak_unrealized_pnl_pct": 2.1, **managed},
                {},
                "KOSPI",
            ),
            "본전보호",
        )

        self.assertEqual(
            _position_exit_reason_by_pnl(
                {"unrealized_pnl_pct": 5.0, "peak_unrealized_pnl_pct": 8.0, **managed},
                {},
                "KOSPI",
            ),
            "트레일링익절",
        )
        self.assertIsNone(
            _position_exit_reason_by_pnl(
                {"unrealized_pnl_pct": 0.0, "peak_unrealized_pnl_pct": 1.99, **managed},
                {},
                "KOSPI",
            )
        )

    def test_legacy_position_without_exit_plan_is_not_auto_stopped(self) -> None:
        self.assertIsNone(
            _position_exit_reason_by_pnl(
                {"unrealized_pnl_pct": -10.0, "last_price_local": 90000, "avg_price_local": 100000},
                {},
                "KOSPI",
            )
        )

    def test_execution_risk_plan_blocks_chased_entry(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "technical_snapshot": {"current_price": 103000},
            "layer_c": {
                "trade_plan": {
                    "entry_price": 100000,
                    "stop_loss": 94000,
                    "take_profit": 114000,
                },
                "invalidation_trigger": {"stop_loss": 94000},
                "technical_features": {"atr14_pct": 2.5},
            },
        }

        plan = _candidate_execution_risk_plan(candidate)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["reason"], "entry_price_chased")

    def test_execution_risk_plan_uses_thesis_stop_and_reward_risk(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "technical_snapshot": {"current_price": 100000},
            "layer_c": {
                "trade_plan": {
                    "entry_price": 100000,
                    "stop_loss": 94000,
                    "take_profit": 112000,
                },
                "invalidation_trigger": {"stop_loss": 94000},
                "technical_features": {"atr14_pct": 2.5},
            },
        }

        plan = _candidate_execution_risk_plan(candidate)

        self.assertTrue(plan["ok"])
        self.assertEqual(plan["stop_loss_pct"], 6.0)
        self.assertEqual(plan["take_profit_pct"], 12.0)
        self.assertEqual(plan["reward_risk"], 2.0)

    def test_execution_risk_plan_blocks_surging_buy_watch(self) -> None:
        candidate = {
            "code": "006340",
            "market": "KOSPI",
            "action": "buy_watch",
            "rating": "overweight",
            "technical_snapshot": {"current_price": 15770, "change_pct": 14.36},
            "layer_c": {
                "action": "buy_watch",
                "rating": "overweight",
                "trade_plan": {
                    "entry_price": 15600,
                    "stop_loss": 14550,
                    "take_profit": 18350,
                },
                "invalidation_trigger": {"stop_loss": 14550},
                "technical_features": {
                    "change_pct": 6.0,
                    "close_vs_sma20": 1.04,
                    "close_vs_sma60": 1.06,
                    "volume_ratio": 1.2,
                },
            },
        }

        plan = _candidate_execution_risk_plan(candidate)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["reason"], "buy_watch_daily_change_too_high")

    def test_refresh_trailing_profit_peak_only_raises_peak(self) -> None:
        position = {"unrealized_pnl_pct": 4.0}
        _refresh_trailing_profit_peak(position)
        self.assertEqual(position["peak_unrealized_pnl_pct"], 4.0)

        position["unrealized_pnl_pct"] = 2.0
        _refresh_trailing_profit_peak(position)
        self.assertEqual(position["peak_unrealized_pnl_pct"], 4.0)

    def test_watch_bluechip_high_score_does_not_rotate(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "watch_only",
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "final_action_snapshot": _buy_agent_snapshot(),
            "layer_c": _buy_research_layer(),
        }

        allowed = _allows_rotation_candidate(
            candidate,
            signal_state="watch",
            entry_allowed=False,
            order_qty=0,
            position_only_blocked=False,
        )

        self.assertFalse(allowed)

    def test_primary_buy_bluechip_can_rotate_when_position_limit_blocks_entry(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "review_for_entry",
            "size_recommendation": {"quantity": 1},
            "final_action_snapshot": _primary_buy_snapshot(),
            "layer_c": _buy_research_layer(),
        }

        allowed = _allows_rotation_candidate(
            candidate,
            signal_state="entry",
            entry_allowed=True,
            order_qty=1,
            position_only_blocked=False,
        )

        self.assertTrue(allowed)

    def test_ordinary_watch_candidate_does_not_rotate(self) -> None:
        candidate = {
            "code": "123456",
            "market": "KOSPI",
            "score": 72,
            "bluechip": False,
            "research_score": 0.4,
            "research_status": "healthy",
            "final_action": "watch_only",
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
        }

        allowed = _allows_rotation_candidate(
            candidate,
            signal_state="watch",
            entry_allowed=False,
            order_qty=0,
            position_only_blocked=False,
        )

        self.assertFalse(allowed)

    def test_primary_buy_bluechip_is_promoted_to_entry_when_slot_and_cash_exist(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "review_for_entry",
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "technical_snapshot": {"current_price": 100000},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 6.0, "reliability": "high"},
            "final_action_snapshot": _primary_buy_snapshot(),
            "layer_c": _buy_research_layer(),
        }
        account = {
            "cash_krw": 10000000,
            "equity_krw": 10000000,
            "positions": [],
        }
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
        }

        promoted = _promote_priority_candidate_for_entry(candidate, account, cfg)

        self.assertTrue(promoted["entry_allowed"])
        self.assertEqual(promoted["active_entry_reason"], "priority_bluechip_entry")
        self.assertGreater(promoted["size_recommendation"]["quantity"], 0)

    def test_operator_review_buy_intent_bluechip_promotes_when_momentum_is_strong(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "signal_state": "entry",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "watch_only",
            "technical_snapshot": {"current_price": 200000},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 1.2, "reliability": "high"},
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "final_action_snapshot": {
                "quant_decision": {"decision": "operator_review", "order_ready": False},
                "agent_decision": {
                    "decision": "agent_primary_buy",
                    "order_ready": True,
                    "rating": "overweight",
                    "action": "buy",
                },
            },
            "layer_c": _buy_research_layer(),
        }
        account = {"cash_krw": 1000000, "equity_krw": 5000000, "positions": []}
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
        }

        promoted = _promote_operator_review_candidate_for_entry(candidate, account, cfg)

        self.assertTrue(promoted["entry_allowed"])
        self.assertEqual(promoted["final_action"], "review_for_entry")
        self.assertEqual(promoted["active_entry_reason"], "operator_review_high_momentum_entry")
        self.assertGreater(promoted["size_recommendation"]["quantity"], 0)

    def test_operator_review_buy_watch_without_agent_approval_is_not_promoted(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "signal_state": "entry",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "watch_only",
            "technical_snapshot": {"current_price": 200000},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 1.2, "reliability": "high"},
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "final_action_snapshot": {
                "quant_decision": {"decision": "operator_review", "order_ready": False},
                "agent_decision": {"decision": "agent_buy_watch", "rating": "overweight", "action": "buy_watch"},
            },
            "layer_c": {
                **_buy_research_layer(),
                "action": "buy_watch",
            },
        }
        account = {"cash_krw": 1000000, "equity_krw": 5000000, "positions": []}
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
        }

        promoted = _promote_operator_review_candidate_for_entry(candidate, account, cfg)

        self.assertFalse(promoted.get("entry_allowed", False))
        self.assertEqual(promoted["final_action"], "watch_only")

    def test_operator_review_surging_buy_watch_is_not_promoted(self) -> None:
        candidate = {
            "code": "006340",
            "market": "KOSPI",
            "signal_state": "entry",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "watch_only",
            "technical_snapshot": {"current_price": 15770, "change_pct": 14.36},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 1.2, "reliability": "high"},
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "final_action_snapshot": {
                "quant_decision": {"decision": "operator_review", "order_ready": False},
                "agent_decision": {
                    "decision": "agent_primary_buy",
                    "order_ready": True,
                    "rating": "overweight",
                    "action": "buy_watch",
                },
            },
            "layer_c": {
                **_buy_research_layer(),
                "action": "buy_watch",
                "technical_features": {
                    "change_pct": 6.0,
                    "close_vs_sma20": 1.04,
                    "close_vs_sma60": 1.06,
                    "volume_ratio": 1.25,
                },
            },
        }
        account = {"cash_krw": 1000000, "equity_krw": 5000000, "positions": []}
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
        }

        promoted = _promote_operator_review_candidate_for_entry(candidate, account, cfg)

        self.assertFalse(promoted.get("entry_allowed", False))
        self.assertEqual(promoted["final_action"], "watch_only")

    def test_operator_review_buy_watch_with_weak_trend_is_not_promoted(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "signal_state": "entry",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "watch_only",
            "technical_snapshot": {"current_price": 200000},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 1.2, "reliability": "high"},
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "final_action_snapshot": {
                "quant_decision": {"decision": "operator_review", "order_ready": False},
                "agent_decision": {"decision": "agent_buy_watch", "rating": "overweight", "action": "buy_watch"},
            },
            "layer_c": {
                **_buy_research_layer(),
                "action": "buy_watch",
                "technical_features": {
                    "close_vs_sma20": 0.97,
                    "close_vs_sma60": 0.96,
                    "volume_ratio": 1.25,
                },
            },
        }
        account = {"cash_krw": 1000000, "equity_krw": 5000000, "positions": []}
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
        }

        promoted = _promote_operator_review_candidate_for_entry(candidate, account, cfg)

        self.assertFalse(promoted.get("entry_allowed", False))
        self.assertEqual(promoted["final_action"], "watch_only")

    def test_operator_review_hold_research_is_not_promoted(self) -> None:
        candidate = {
            "code": "005930",
            "market": "KOSPI",
            "signal_state": "entry",
            "score": 99,
            "bluechip": True,
            "research_score": 0.86,
            "research_status": "healthy",
            "final_action": "watch_only",
            "technical_snapshot": {"current_price": 80000},
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "final_action_snapshot": {
                "quant_decision": {"decision": "operator_review", "order_ready": False},
                "agent_decision": {"decision": "agent_hold", "rating": "hold", "action": "hold"},
            },
            "layer_c": {
                "rating": "hold",
                "action": "hold",
                "technical_features": {
                    "close_vs_sma20": 1.05,
                    "close_vs_sma60": 1.06,
                    "volume_ratio": 1.5,
                },
            },
        }
        account = {"cash_krw": 1000000, "equity_krw": 5000000, "positions": []}
        cfg = {"allocation_mode": "concentrated"}

        promoted = _promote_operator_review_candidate_for_entry(candidate, account, cfg)

        self.assertFalse(promoted.get("entry_allowed", False))
        self.assertEqual(promoted["final_action"], "watch_only")

    def test_rotation_runs_when_slots_remain_but_priority_candidate_needs_cash(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "review_for_entry",
            "size_recommendation": {"quantity": 0, "reason": "exposure_or_cash_limit"},
            "final_action_snapshot": _primary_buy_snapshot(),
            "layer_c": _buy_research_layer(),
        }

        self.assertTrue(_should_attempt_rotation(1, [candidate]))

    def test_unit_price_uses_research_technical_features_when_quote_missing(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "technical_snapshot": {"quote_error": "token_limited"},
            "layer_c": {
                "technical_features": {"current_price": 289000},
            },
        }

        self.assertEqual(_candidate_unit_price_local(candidate), 289000)

    def test_blocked_priority_candidate_does_not_rotate_when_block_is_size_related(self) -> None:
        candidate = {
            "code": "000660",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "blocked",
            "size_recommendation": {"quantity": 0, "reason": "invalid_unit_price"},
            "final_action_snapshot": {
                "agent_decision": {"decision": "agent_primary_buy", "rating": "overweight", "action": "buy"},
            },
            "layer_c": _buy_research_layer(),
        }

        self.assertFalse(_should_attempt_rotation(1, [candidate]))

    def test_hold_research_candidate_does_not_rotate_even_when_quant_score_is_high(self) -> None:
        candidate = {
            "code": "034020",
            "market": "KOSPI",
            "score": 91,
            "bluechip": True,
            "research_score": 0.62,
            "research_status": "healthy",
            "final_action": "review_for_entry",
            "size_recommendation": {"quantity": 1, "reason": "ok"},
            "final_action_snapshot": {
                "agent_decision": {"decision": "agent_hold", "rating": "hold", "action": "hold"},
            },
            "layer_c": {
                "rating": "hold",
                "action": "hold",
                "technical_features": {
                    "close_vs_sma20": 1.02,
                    "close_vs_sma60": 1.04,
                    "volume_ratio": 1.1,
                },
            },
        }

        self.assertFalse(
            _allows_rotation_candidate(
                candidate,
                signal_state="watch",
                entry_allowed=False,
                order_qty=1,
                position_only_blocked=False,
            )
        )

    def test_weak_trend_candidate_does_not_rotate_even_when_bluechip_score_is_high(self) -> None:
        candidate = {
            "code": "034020",
            "market": "KOSPI",
            "score": 91,
            "bluechip": True,
            "research_score": 0.82,
            "research_status": "healthy",
            "final_action": "watch_only",
            "size_recommendation": {"quantity": 0, "reason": "signal_only"},
            "final_action_snapshot": _primary_buy_snapshot(),
            "layer_c": {
                "rating": "overweight",
                "action": "buy",
                "technical_features": {
                    "close_vs_sma20": 0.94,
                    "close_vs_sma60": 0.88,
                    "volume_ratio": 0.42,
                },
            },
        }

        self.assertFalse(
            _allows_rotation_candidate(
                candidate,
                signal_state="watch",
                entry_allowed=False,
                order_qty=0,
                position_only_blocked=False,
            )
        )

    def test_positive_change_and_volume_rank_a_candidate_first(self) -> None:
        leader = {
            "code": "000660",
            "score": 90,
            "research_score": 0.7,
            "technical_snapshot": {"change_pct": 4.2},
            "layer_c": {
                "technical_features": {
                    "close_vs_sma20": 1.05,
                    "close_vs_sma60": 1.08,
                    "volume_ratio": 1.7,
                },
            },
        }
        laggard = {
            "code": "034020",
            "score": 95,
            "research_score": 0.8,
            "technical_snapshot": {"change_pct": -1.1},
            "layer_c": {
                "technical_features": {
                    "close_vs_sma20": 1.01,
                    "close_vs_sma60": 1.02,
                    "volume_ratio": 1.0,
                },
            },
        }

        ranked = sorted([laggard, leader], key=_candidate_leadership_rank, reverse=True)

        self.assertEqual(ranked[0]["code"], "000660")

    def test_rotation_plan_ignores_candidate_that_only_sizes_after_selling(self) -> None:
        now = datetime.now(timezone.utc)
        account = {
            "cash_krw": 1000,
            "equity_krw": 2000000,
            "market_value_krw": 1000000,
            "positions": [
                {
                    "code": "111111",
                    "name": "약한보유",
                    "market": "KOSPI",
                    "quantity": 1,
                    "entry_ts": (now - timedelta(days=3)).isoformat(),
                    "market_value_krw": 1000000,
                    "last_price_local": 1000000,
                    "entry_plan_price": 1000000,
                    "stop_loss_price": 940000,
                    "take_profit_price": 1120000,
                    "orderable_quantity": 1,
                }
            ],
        }
        candidate = {
            "code": "000660",
            "name": "SK하이닉스",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.86,
            "research_status": "healthy",
            "final_action": "review_for_entry",
            "technical_snapshot": {"current_price": 200000},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 1.2, "reliability": "high"},
            "size_recommendation": {"quantity": 0, "reason": "exposure_or_cash_limit"},
            "final_action_snapshot": _primary_buy_snapshot(),
            "layer_c": _buy_research_layer(),
        }
        signal_map = {
            "111111": {"code": "111111", "market": "KOSPI", "score": 90},
            "000660": candidate,
        }
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
            "rotation": {"enabled": True, "min_score_gap": 2.0, "daily_limit": 0, "min_holding_minutes": 30},
        }

        plan = _select_rotation_plan(
            account=account,
            market="KOSPI",
            cfg=cfg,
            rotation_candidates=[candidate],
            signal_map=signal_map,
            held_codes={"111111"},
            strategy_position_counts={},
            strategy_position_caps={},
            max_orders_per_symbol=3,
        )

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["reason"], "rotation_no_buy_candidate")

    def test_rotation_plan_respects_min_holding_minutes(self) -> None:
        now = datetime.now(timezone.utc)
        account = {
            "cash_krw": 1000000,
            "equity_krw": 2000000,
            "market_value_krw": 1000000,
            "positions": [
                {
                    "code": "111111",
                    "name": "방금산보유",
                    "market": "KOSPI",
                    "quantity": 1,
                    "entry_ts": (now - timedelta(minutes=5)).isoformat(),
                    "market_value_krw": 1000000,
                    "last_price_local": 1000000,
                    "entry_plan_price": 1000000,
                    "stop_loss_price": 940000,
                    "take_profit_price": 1120000,
                    "orderable_quantity": 1,
                }
            ],
        }
        candidate = {
            "code": "000660",
            "name": "SK하이닉스",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.86,
            "research_status": "healthy",
            "final_action": "review_for_entry",
            "technical_snapshot": {"current_price": 200000},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 1.2, "reliability": "high"},
            "size_recommendation": {"quantity": 1},
            "final_action_snapshot": _primary_buy_snapshot(),
            "layer_c": _buy_research_layer(),
        }
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
            "rotation": {"enabled": True, "min_score_gap": 2.0, "daily_limit": 0, "min_holding_minutes": 30},
        }

        plan = _select_rotation_plan(
            account=account,
            market="KOSPI",
            cfg=cfg,
            rotation_candidates=[candidate],
            signal_map={"111111": {"code": "111111", "market": "KOSPI", "score": 90}},
            held_codes={"111111"},
            strategy_position_counts={},
            strategy_position_caps={},
            max_orders_per_symbol=3,
        )

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["reason"], "rotation_no_sellable_position")

    def test_rotation_plan_excludes_legacy_position_without_exit_plan(self) -> None:
        now = datetime.now(timezone.utc)
        account = {
            "cash_krw": 1000000,
            "equity_krw": 2000000,
            "market_value_krw": 1000000,
            "positions": [
                {
                    "code": "111111",
                    "name": "기존보유",
                    "market": "KOSPI",
                    "quantity": 1,
                    "entry_ts": (now - timedelta(hours=2)).isoformat(),
                    "market_value_krw": 1000000,
                    "last_price_local": 900000,
                    "orderable_quantity": 1,
                }
            ],
        }
        candidate = {
            "code": "000660",
            "name": "SK하이닉스",
            "market": "KOSPI",
            "score": 98,
            "bluechip": True,
            "research_score": 0.86,
            "research_status": "healthy",
            "final_action": "review_for_entry",
            "technical_snapshot": {"current_price": 200000},
            "risk_inputs": {"stop_loss_pct": 5},
            "ev_metrics": {"expected_value": 1.2, "reliability": "high"},
            "size_recommendation": {"quantity": 1},
            "final_action_snapshot": _primary_buy_snapshot(),
            "layer_c": _buy_research_layer(),
        }
        cfg = {
            "allocation_mode": "concentrated",
            "risk_per_trade_pct": 0.8,
            "bluechip_risk_per_trade_pct": 1.5,
            "max_symbol_weight_pct": 30.0,
            "max_sector_weight_pct": 50.0,
            "max_market_exposure_pct": 95.0,
            "rotation": {"enabled": True, "min_score_gap": 2.0, "daily_limit": 0, "min_holding_minutes": 30},
        }

        plan = _select_rotation_plan(
            account=account,
            market="KOSPI",
            cfg=cfg,
            rotation_candidates=[candidate],
            signal_map={"111111": {"code": "111111", "market": "KOSPI", "score": 90}},
            held_codes={"111111"},
            strategy_position_counts={},
            strategy_position_caps={},
            max_orders_per_symbol=3,
        )

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["reason"], "rotation_no_sellable_position")


if __name__ == "__main__":
    unittest.main()
