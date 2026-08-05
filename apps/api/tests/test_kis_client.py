from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from broker.kis_client import KISClient, KISCredentials, _read_json_file, _write_json_file


class KISClientTests(unittest.TestCase):
    def test_access_token_issue_limit_is_rate_limit_error(self) -> None:
        payload = {
            "error_code": "EGW00133",
            "error_description": "접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)",
        }

        self.assertTrue(KISClient._is_rate_limit_error(payload))

    def test_write_json_file_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "token.json"

            _write_json_file(path, {"access_token": "abc"})

            self.assertEqual(_read_json_file(path), {"access_token": "abc"})

    def test_domestic_daily_fills_normalizes_exact_kis_fill(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com", "12345678", "01"))
        response = Mock(headers={})
        client._auth_headers = Mock(return_value={})
        client._request_full = Mock(return_value=({
            "output1": [{
                "ord_dt": "20260805", "ord_tmd": "093949", "ord_gno_brno": "12345", "odno": "1002",
                "sll_buy_dvsn_cd": "01", "pdno": "006340", "prdt_name": "대원전선",
                "tot_ccld_qty": "16", "avg_prvs": "15720", "tot_ccld_amt": "251520",
            }],
            "output2": {
                "tot_ccld_qty": "16", "tot_ccld_amt": "251520", "prsm_tlex_smtl": "520",
            },
        }, response))

        result = client.get_domestic_daily_fills("2026-08-05")

        self.assertEqual(result["summary"]["fees_and_tax_krw"], 520)
        self.assertEqual(result["orders"][0]["side"], "sell")
        self.assertEqual(result["orders"][0]["filled_price_krw"], 15720)
        self.assertEqual(result["orders"][0]["filled_at"], "2026-08-05T09:39:49+09:00")

    def test_domestic_period_trade_profit_normalizes_exact_realized_pnl(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com", "12345678", "01"))
        response = Mock(headers={})
        client._auth_headers = Mock(return_value={})
        client._request_full = Mock(return_value=({
            "output1": [{
                "trad_dt": "20260805", "pdno": "006340", "prdt_name": "대원전선",
                "pchs_unpr": "15760", "buy_qty": "16", "buy_amt": "252160",
                "sll_pric": "15720", "sll_qty": "16", "sll_amt": "251520",
                "rlzt_pfls": "-1160", "pfls_rt": "-0.46002538", "fee": "18", "tl_tax": "502",
            }],
            "output2": {"tot_rlzt_pfls": "-1160", "tot_fee": "18", "tot_tltx": "502"},
        }, response))

        result = client.get_domestic_period_trade_profit("2026-08-05")

        self.assertEqual(result["trades"][0]["realized_pnl_krw"], -1160)
        self.assertEqual(result["trades"][0]["total_cost_krw"], 520)
        self.assertEqual(result["summary"]["realized_pnl_krw"], -1160)

    def test_domestic_daily_fills_uses_next_page_header(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com", "12345678", "01"))
        client._auth_headers = Mock(return_value={})
        client._request_full = Mock(side_effect=[
            ({
                "output1": [],
                "output2": {"prsm_tlex_smtl": "0"},
                "ctx_area_fk100": "next-fk",
                "ctx_area_nk100": "next-nk",
            }, Mock(headers={"tr_cont": "M"})),
            ({
                "output1": [],
                "output2": {"prsm_tlex_smtl": "0"},
            }, Mock(headers={})),
        ])

        client.get_domestic_daily_fills("2026-08-05")

        second_call = client._request_full.call_args_list[1]
        self.assertEqual(second_call.kwargs["headers"]["tr_cont"], "N")
        self.assertEqual(second_call.kwargs["params"]["CTX_AREA_FK100"], "next-fk")
        self.assertEqual(second_call.kwargs["params"]["CTX_AREA_NK100"], "next-nk")

    def test_domestic_period_profit_uses_next_page_header(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com", "12345678", "01"))
        client._auth_headers = Mock(return_value={})
        client._request_full = Mock(side_effect=[
            ({
                "output1": [],
                "output2": {},
                "ctx_area_fk100": "next-fk",
                "ctx_area_nk100": "next-nk",
            }, Mock(headers={"tr_cont": "F"})),
            ({"output1": [], "output2": {}}, Mock(headers={})),
        ])

        client.get_domestic_period_trade_profit("2026-08-05")

        second_call = client._request_full.call_args_list[1]
        self.assertEqual(second_call.kwargs["headers"]["tr_cont"], "N")
        self.assertEqual(second_call.kwargs["params"]["CTX_AREA_FK100"], "next-fk")
        self.assertEqual(second_call.kwargs["params"]["CTX_AREA_NK100"], "next-nk")


if __name__ == "__main__":
    unittest.main()
