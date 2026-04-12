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

from services import market_data_service as svc


class FakeClient:
    def get_overseas_price(self, symbol: str, *, exchange: str = "NASDAQ"):
        if exchange == "NASDAQ":
            return {"price": None, "name": "", "change_pct": None}
        if exchange == "NYSE":
            return {"price": 268.73, "name": "Wabtec", "change_pct": -0.82}
        raise RuntimeError("unexpected exchange")


class MarketDataServiceTests(unittest.TestCase):
    def test_resolve_stock_quote_retries_next_exchange_when_price_is_empty(self):
        with patch.object(svc, "lookup_company_listing", return_value={"code": "WAB", "name": "Wabtec", "market": "NASDAQ"}), \
             patch.object(svc, "_get_kis_client", return_value=FakeClient()):
            quote = svc.resolve_stock_quote("WAB", "NASDAQ")

        self.assertEqual(268.73, quote["price"])
        self.assertEqual("NYSE", quote["market"])
        self.assertEqual("Wabtec", quote["name"])


if __name__ == "__main__":
    unittest.main()