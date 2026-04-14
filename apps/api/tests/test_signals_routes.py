from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from routes.signals import _load_runtime_account, handle_signals_rank


class _FakeExecutionService:
    def __init__(self) -> None:
        self.paper_account_calls: list[bool] = []

    def paper_account(self, refresh_quotes: bool) -> tuple[int, dict]:
        self.paper_account_calls.append(refresh_quotes)
        return 200, {
            "account": {
                "positions": [{"code": "005930", "qty": 1}],
                "cash_krw": 1000000,
            }
        }


class SignalsRouteTests(unittest.TestCase):
    def test_load_runtime_account_uses_refresh_quotes_signature(self):
        service = _FakeExecutionService()

        with patch("routes.signals.get_execution_service", return_value=service):
            account = _load_runtime_account()

        self.assertEqual([True], service.paper_account_calls)
        self.assertEqual(
            {
                "positions": [{"code": "005930", "qty": 1}],
                "cash_krw": 1000000,
            },
            account,
        )

    def test_handle_signals_rank_trims_signal_list_after_loading_runtime_account(self):
        service = _FakeExecutionService()
        signal_book = {
            "ok": True,
            "signals": [
                {"code": "AAPL", "score": 95},
                {"code": "MSFT", "score": 93},
            ],
        }

        with (
            patch("routes.signals.get_execution_service", return_value=service),
            patch("routes.signals.build_signal_book", return_value=signal_book) as mock_build_signal_book,
        ):
            status, payload = handle_signals_rank({"limit": ["1"]})

        self.assertEqual(200, status)
        self.assertEqual([True], service.paper_account_calls)
        self.assertEqual(1, payload["count"])
        self.assertEqual([{"code": "AAPL", "score": 95}], payload["signals"])
        self.assertTrue(payload["ok"])
        mock_build_signal_book.assert_called_once_with(markets=None, cfg={}, account={
            "positions": [{"code": "005930", "qty": 1}],
            "cash_krw": 1000000,
        })


if __name__ == "__main__":
    unittest.main()
