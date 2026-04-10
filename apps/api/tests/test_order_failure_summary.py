from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

if "holidays" not in sys.modules:
    sys.modules["holidays"] = types.SimpleNamespace(KR=lambda *args, **kwargs: set(), US=lambda *args, **kwargs: set())

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import execution_service as execution_svc


class OrderFailureSummaryTests(unittest.TestCase):
    def test_screened_non_orders_are_excluded_from_failure_summary(self):
        rows = [
            {
                "timestamp": "2026-04-10T10:00:00+09:00",
                "success": False,
                "order_type": "screened",
                "failure_reason": "do_not_touch",
                "market": "KOSPI",
                "code": "005930",
            },
            {
                "timestamp": "2026-04-10T10:01:00+09:00",
                "success": False,
                "order_type": "market",
                "failure_reason": "liquidity_too_low",
                "market": "KOSPI",
                "code": "000660",
            },
        ]
        with patch.object(execution_svc, "_today_kst_str", return_value="2026-04-10"), \
             patch.object(execution_svc, "read_order_events", return_value=rows):
            summary = execution_svc._order_failure_summary()

        self.assertEqual(1, summary["today_failed"])
        self.assertEqual("liquidity_too_low", summary["top_reason"])
        self.assertEqual("liquidity_too_low", summary["latest_failure_reason"])


if __name__ == "__main__":
    unittest.main()
