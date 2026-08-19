from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from api_server import _allowed_browser_origins, _browser_request_allowed


class APISecurityBoundaryTests(unittest.TestCase):
    def test_default_origins_only_allow_local_web_console(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                _allowed_browser_origins(),
                {"http://127.0.0.1:8081", "http://localhost:8081"},
            )
            self.assertTrue(_browser_request_allowed("http://localhost:8081", "same-origin"))
            self.assertFalse(_browser_request_allowed("https://evil.example", "cross-site"))

    def test_cross_site_header_is_rejected_even_without_origin(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_browser_request_allowed("", "cross-site"))

    def test_cli_request_without_browser_headers_remains_allowed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(_browser_request_allowed("", ""))

    def test_custom_origin_list_is_normalized_and_invalid_values_are_ignored(self) -> None:
        with patch.dict(
            os.environ,
            {"WEALTHPULSE_ALLOWED_ORIGINS": "https://console.example/,not-a-url,http://localhost:8081"},
            clear=True,
        ):
            self.assertEqual(
                _allowed_browser_origins(),
                {"https://console.example", "http://localhost:8081"},
            )
            self.assertTrue(_browser_request_allowed("https://console.example/", "same-site"))
            self.assertFalse(_browser_request_allowed("https://other.example", "same-site"))


if __name__ == "__main__":
    unittest.main()
