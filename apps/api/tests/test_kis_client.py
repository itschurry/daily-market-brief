from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from requests import Timeout


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from broker.kis_client import KISAPIError, KISClient, KISCredentials, KISRequestAuditError, _read_json_file, _write_json_file


class KISClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self._audit_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._audit_tmpdir.cleanup)
        audit_path = Path(self._audit_tmpdir.name) / "kis_requests.jsonl"
        audit_patcher = patch.object(KISClient, "_REQUEST_AUDIT_PATH", audit_path)
        audit_patcher.start()
        self.addCleanup(audit_patcher.stop)

    def _successful_response(self) -> Mock:
        response = Mock(headers={})
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {"rt_cd": "0"}
        return response

    def test_request_audit_is_append_only_and_excludes_sensitive_values(self) -> None:
        client = KISClient(KISCredentials("app-key", "app-secret", "https://example.com"))
        success_response = self._successful_response()
        limited_response = self._successful_response()
        limited_response.json.return_value = {
            "rt_cd": "1",
            "msg_cd": "EGW00215",
            "msg1": "원장에서 허용 가능한 초당 거래건수를 초과하였습니다.",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            audit_path = Path(tmpdir) / "kis_requests.jsonl"
            headers = {
                "authorization": "Bearer private-token",
                "appkey": "app-key",
                "appsecret": "app-secret",
                "tr_id": "TTTC8434R",
            }
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch.object(KISClient, "_REQUEST_AUDIT_PATH", audit_path),
                patch("broker.kis_client.time.sleep"),
                patch(
                    "broker.kis_client.requests.request",
                    side_effect=[success_response, limited_response],
                ),
            ):
                client._request(
                    "GET",
                    "/uapi/domestic-stock/v1/trading/inquire-balance",
                    headers=headers,
                    params={"CANO": "12345678", "ACNT_PRDT_CD": "01"},
                )
                with self.assertRaisesRegex(KISAPIError, "EGW00215"):
                    client._request(
                        "GET",
                        "/uapi/domestic-stock/v1/trading/inquire-balance",
                        headers=headers,
                        params={"CANO": "12345678", "ACNT_PRDT_CD": "01"},
                    )

            raw_audit = audit_path.read_text(encoding="utf-8")
            records = [json.loads(line) for line in raw_audit.splitlines()]

        self.assertEqual(len(records), 2)
        self.assertTrue(records[0]["success"])
        self.assertFalse(records[1]["success"])
        self.assertEqual(records[1]["kis_msg_cd"], "EGW00215")
        self.assertEqual(
            records[1]["kis_msg1"],
            "원장에서 허용 가능한 초당 거래건수를 초과하였습니다.",
        )
        self.assertEqual(records[1]["http_status_code"], 200)
        self.assertEqual(records[1]["tr_id"], "TTTC8434R")
        self.assertEqual(records[1]["method"], "GET")
        self.assertEqual(records[1]["request_class"], "trading")
        self.assertTrue(records[1]["request_id"])
        self.assertGreater(records[1]["pid"], 0)
        self.assertTrue(records[1]["hostname"])
        self.assertTrue(records[1]["thread_name"])
        self.assertEqual(
            records[1]["path"],
            "/uapi/domestic-stock/v1/trading/inquire-balance",
        )
        self.assertTrue(records[1]["started_at"])
        self.assertTrue(records[1]["completed_at"])
        self.assertGreaterEqual(records[1]["lock_wait_seconds"], 0.0)
        self.assertGreater(records[1]["throttle_wait_seconds"], 0.0)
        for sensitive_value in (
            "private-token",
            "app-key",
            "app-secret",
            "12345678",
            "ACNT_PRDT_CD",
            "authorization",
            "params",
            "json_body",
        ):
            self.assertNotIn(sensitive_value, raw_audit)

    def test_access_token_issue_limit_is_rate_limit_error(self) -> None:
        payload = {
            "error_code": "EGW00133",
            "error_description": "접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)",
        }

        self.assertTrue(KISClient._is_rate_limit_error(payload))

    def test_request_audit_failure_fails_closed(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        response = self._successful_response()
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            invalid_audit_path = Path(tmpdir)
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch.object(KISClient, "_REQUEST_AUDIT_PATH", invalid_audit_path),
                patch("broker.kis_client.requests.request", return_value=response) as request_mock,
            ):
                with self.assertRaisesRegex(
                    KISRequestAuditError,
                    "브로커 처리 결과 확인 필요",
                ):
                    client._request(
                        "GET",
                        "/uapi/domestic-stock/v1/quotations/inquire-price",
                    )

        request_mock.assert_called_once()

    def test_network_exception_audit_records_only_exception_type(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            audit_path = Path(tmpdir) / "kis_requests.jsonl"
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch.object(KISClient, "_REQUEST_AUDIT_PATH", audit_path),
                patch(
                    "broker.kis_client.requests.request",
                    side_effect=Timeout("private-token 12345678"),
                ),
            ):
                with self.assertRaises(Timeout):
                    client._request(
                        "GET",
                        "/uapi/domestic-stock/v1/quotations/inquire-price",
                    )

            raw_audit = audit_path.read_text(encoding="utf-8")
            record = json.loads(raw_audit)

        self.assertFalse(record["success"])
        self.assertEqual(record["exception_type"], "Timeout")
        self.assertNotIn("private-token", raw_audit)
        self.assertNotIn("12345678", raw_audit)

    def test_request_exception_is_replaced_by_fail_closed_audit_error(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch.object(KISClient, "_REQUEST_AUDIT_PATH", Path(tmpdir)),
                patch(
                    "broker.kis_client.requests.request",
                    side_effect=Timeout("timed out"),
                ) as request_mock,
            ):
                with self.assertRaisesRegex(
                    KISRequestAuditError,
                    "브로커 처리 결과 확인 필요",
                ):
                    client._request(
                        "GET",
                        "/uapi/domestic-stock/v1/quotations/inquire-price",
                    )

        request_mock.assert_called_once()

    def test_ledger_rate_limit_codes_fail_without_retry(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        payloads = [
            {"rt_cd": "1", "msg_cd": "EGW00201", "msg1": "초당 거래건수를 초과하였습니다."},
            {"rt_cd": "1", "msg_cd": "EGW00215", "msg1": "원장에서 허용 가능한 초당 거래건수를 초과하였습니다."},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            for payload in payloads:
                response = self._successful_response()
                response.json.return_value = payload
                with (
                    self.subTest(code=payload["msg_cd"]),
                    patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                    patch("broker.kis_client.requests.request", return_value=response) as request_mock,
                ):
                    budget_path.unlink(missing_ok=True)
                    with self.assertRaisesRegex(KISAPIError, payload["msg_cd"]):
                        client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")
                    request_mock.assert_called_once()
                    self.assertTrue(KISClient._is_rate_limit_error(payload))

    def test_requests_are_serialized_across_client_instances(self) -> None:
        active = 0
        max_active = 0
        active_lock = threading.Lock()

        def request_side_effect(**_: object) -> Mock:
            nonlocal active, max_active
            with active_lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.03)
            with active_lock:
                active -= 1
            return self._successful_response()

        clients = [
            KISClient(KISCredentials("key", "secret", "https://example.com")),
            KISClient(KISCredentials("key", "secret", "https://example.com")),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch("broker.kis_client.requests.request", side_effect=request_side_effect),
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(
                        lambda client: client._request(
                            "GET",
                            "/uapi/domestic-stock/v1/quotations/inquire-price",
                        ),
                        clients,
                    ))

        self.assertEqual(results, [{"rt_cd": "0"}, {"rt_cd": "0"}])
        self.assertEqual(max_active, 1)

    def test_trading_requests_enforce_buffered_shared_interval(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        response = self._successful_response()
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch("broker.kis_client.requests.request", return_value=response),
                patch("broker.kis_client.time.sleep") as sleep_mock,
            ):
                client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")
                client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")

        self.assertTrue(any(call.args and call.args[0] > 1.1 for call in sleep_mock.call_args_list))

    def test_trading_interval_starts_after_previous_response_completes(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        clock = 100.0
        request_started_at: list[float] = []

        def fake_time() -> float:
            return clock

        def fake_sleep(seconds: float) -> None:
            nonlocal clock
            clock += seconds

        def request_side_effect(**_: object) -> Mock:
            nonlocal clock
            request_started_at.append(clock)
            clock += 0.4
            return self._successful_response()

        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch("broker.kis_client.KIS_TRADING_REQUEST_INTERVAL_SECONDS", 1.2),
                patch("broker.kis_client.time.time", side_effect=fake_time),
                patch("broker.kis_client.time.sleep", side_effect=fake_sleep),
                patch("broker.kis_client.requests.request", side_effect=request_side_effect),
            ):
                client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")
                first_completed_at = clock
                client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")

            state = _read_json_file(budget_path)

        self.assertEqual(len(request_started_at), 2)
        self.assertGreaterEqual(request_started_at[1] - first_completed_at, 1.2 - 1e-9)
        self.assertEqual(state["last_trading_request_at"], clock)

    def test_trading_interval_is_preserved_after_request_timeout(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        clock = 200.0
        request_started_at: list[float] = []

        def fake_time() -> float:
            return clock

        def fake_sleep(seconds: float) -> None:
            nonlocal clock
            clock += seconds

        def request_side_effect(**_: object) -> Mock:
            nonlocal clock
            request_started_at.append(clock)
            clock += 0.4
            if len(request_started_at) == 1:
                raise Timeout("timed out")
            return self._successful_response()

        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch("broker.kis_client.KIS_TRADING_REQUEST_INTERVAL_SECONDS", 1.2),
                patch("broker.kis_client.time.time", side_effect=fake_time),
                patch("broker.kis_client.time.sleep", side_effect=fake_sleep),
                patch("broker.kis_client.requests.request", side_effect=request_side_effect),
            ):
                with self.assertRaises(Timeout):
                    client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")
                failed_request_completed_at = clock
                client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")

        self.assertEqual(len(request_started_at), 2)
        self.assertGreaterEqual(request_started_at[1] - failed_request_completed_at, 1.2 - 1e-9)

    def test_future_request_budget_timestamp_fails_closed(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        with tempfile.TemporaryDirectory() as tmpdir:
            budget_path = Path(tmpdir) / "kis_request_budget.lock"
            _write_json_file(budget_path, {
                "last_request_at": 101.0,
                "last_trading_request_at": 101.0,
            })
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", budget_path),
                patch("broker.kis_client.time.time", return_value=100.0),
                patch("broker.kis_client.requests.request") as request_mock,
            ):
                with self.assertRaisesRegex(KISAPIError, "cannot be in the future"):
                    client._request("GET", "/uapi/domestic-stock/v1/trading/inquire-balance")
                request_mock.assert_not_called()

    def test_request_budget_lock_failure_does_not_bypass_limit(self) -> None:
        client = KISClient(KISCredentials("key", "secret", "https://example.com"))
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_budget_path = Path(tmpdir)
            with (
                patch.object(KISClient, "_REQUEST_BUDGET_PATH", invalid_budget_path),
                patch("broker.kis_client.requests.request") as request_mock,
            ):
                with self.assertRaisesRegex(KISAPIError, "KIS 호출 예산 잠금 실패"):
                    client._request("GET", "/uapi/domestic-stock/v1/quotations/inquire-price")
                request_mock.assert_not_called()

    def test_write_json_file_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "token.json"

            _write_json_file(path, {"access_token": "abc"})

            self.assertEqual(_read_json_file(path), {"access_token": "abc"})

    def test_get_sellable_quantity_uses_official_domestic_sell_endpoint(self) -> None:
        client = KISClient(
            KISCredentials(
                "key",
                "secret",
                "https://example.com",
                "12345678",
                "01",
            )
        )
        client._auth_headers = Mock(return_value={"tr_id": "TTTC8408R"})
        client._request = Mock(return_value={
            "output": {
                "ord_psbl_qty": "8",
                "cblc_qty": "11",
            }
        })

        result = client.get_sellable_quantity("005380")

        self.assertEqual(result["sellable_quantity"], 8)
        self.assertEqual(result["balance_quantity"], 11)
        client._auth_headers.assert_called_once_with("TTTC8408R")
        client._request.assert_called_once_with(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-psbl-sell",
            headers={"tr_id": "TTTC8408R"},
            params={
                "CANO": "12345678",
                "ACNT_PRDT_CD": "01",
                "PDNO": "005380",
            },
        )

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
