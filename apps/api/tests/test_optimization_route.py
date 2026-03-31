from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

quant_ops_stub = types.ModuleType("services.quant_ops_service")
quant_ops_stub.register_optimizer_search_handoff = lambda payload=None: payload
quant_ops_stub.finalize_optimizer_search_handoff = lambda **kwargs: {"ok": True, **kwargs}
sys.modules["services.quant_ops_service"] = quant_ops_stub

from routes import optimization as route  # noqa: E402


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, **_: object) -> None:
        self._target = target
        self.daemon = daemon

    def start(self) -> None:
        if self._target is not None:
            self._target()


class OptimizationRouteTests(unittest.TestCase):
    def tearDown(self) -> None:
        route._optimization_running = False

    def test_run_optimization_uses_api_script_path_and_saved_settings(self):
        commands: list[list[str]] = []

        class _FakePopen:
            def __init__(self, command, stdout=None, stderr=None):
                commands.append(list(command))
                self.pid = 43210
                self.returncode = 0

            def wait(self, timeout=None):
                self.returncode = 0
                return 0

        payload = {
            "query": {"market_scope": "nasdaq"},
            "settings": {"trainingDays": 180, "validationDays": 60},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            flag_path = Path(tmpdir) / "optimization_running"
            log_path = Path(tmpdir) / "optimization.log"
            with patch.object(route, "_OPT_RUNNING_FLAG", flag_path), \
                 patch.object(route, "_LOG_PATH", log_path), \
                 patch.object(route, "register_optimizer_search_handoff") as mock_register, \
                 patch.object(route, "finalize_optimizer_search_handoff", return_value={"ok": True}) as mock_finalize, \
                 patch.object(route.threading, "Thread", _ImmediateThread), \
                 patch.object(route.subprocess, "Popen", _FakePopen):
                status, response = route.handle_run_optimization(payload)

        self.assertEqual(200, status)
        self.assertEqual("started", response["status"])
        self.assertEqual(1, len(commands))
        self.assertEqual(sys.executable, commands[0][0])
        self.assertEqual(str(route._optimizer_script_path()), commands[0][1])
        self.assertIn("--market", commands[0])
        self.assertIn("NASDAQ", commands[0])
        self.assertIn("180", commands[0])
        self.assertIn("60", commands[0])
        mock_register.assert_called_once_with(payload)
        mock_finalize.assert_called_once_with(success=True)


if __name__ == "__main__":
    unittest.main()
