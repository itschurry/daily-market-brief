import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


class ResearchLoopContractTest(unittest.TestCase):
    def test_compose_recovers_research_loop_after_host_restart(self) -> None:
        compose_path = REPO_ROOT / "docker-compose.yml"
        if not compose_path.exists():
            self.skipTest("docker-compose.yml is not packaged in the API image")

        compose = compose_path.read_text(encoding="utf-8")

        service = re.search(
            r"(?ms)^  research-loop:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
            compose,
        )

        self.assertIsNotNone(service)
        self.assertRegex(service.group("body"), r"(?m)^    restart: unless-stopped$")
        self.assertIn("wealthpulse-research-loop.fail-stopped", service.group("body"))
        self.assertIn("WEALTHPULSE_RESEARCH_FAIL_STOP_MARKER", service.group("body"))

    def test_system_failure_stays_alive_without_restart_loop(self) -> None:
        script_path = REPO_ROOT / "scripts" / "run_market_research_loop.sh"
        if not script_path.exists():
            self.skipTest("research loop script is not packaged in the API image")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            marker_path = temp_path / "research-loop.fail-stopped"
            marker_path.write_text("previous_failure\n", encoding="utf-8")
            env = {
                **os.environ,
                "LOGS_DIR": str(temp_path / "logs"),
                "WEALTHPULSE_RESEARCH_LOOP_INTERVAL_SECONDS": "invalid",
                "WEALTHPULSE_RESEARCH_FAIL_STOP_MARKER": str(marker_path),
            }
            process = subprocess.Popen(
                [str(script_path)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if (
                        marker_path.exists()
                        and marker_path.read_text(encoding="utf-8").strip() == "invalid_interval"
                    ):
                        break
                    time.sleep(0.05)

                self.assertTrue(marker_path.exists())
                self.assertEqual(marker_path.read_text(encoding="utf-8").strip(), "invalid_interval")
                self.assertIsNone(process.poll())
            finally:
                process.terminate()
                process.wait(timeout=3)

            self.assertEqual(process.returncode, 0)

    def test_term_is_forwarded_to_running_research_runner(self) -> None:
        source_script = REPO_ROOT / "scripts" / "run_market_research_loop.sh"
        if not source_script.exists():
            self.skipTest("research loop script is not packaged in the API image")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            scripts_path = temp_path / "scripts"
            scripts_path.mkdir()
            loop_script = scripts_path / "run_market_research_loop.sh"
            runner_script = scripts_path / "run_market_research.sh"
            grandchild_script = scripts_path / "research-child.sh"
            python_script = temp_path / "market-status-python"
            ready_path = temp_path / "runner.ready"
            signal_path = temp_path / "runner.signal"
            grandchild_ready_path = temp_path / "grandchild.ready"
            grandchild_signal_path = temp_path / "grandchild.signal"

            shutil.copy2(source_script, loop_script)
            grandchild_script.write_text(
                "#!/usr/bin/env bash\n"
                "trap 'printf term > \"$GRANDCHILD_SIGNAL_FILE\"; exit 0' TERM INT\n"
                "printf ready > \"$GRANDCHILD_READY_FILE\"\n"
                "while true; do sleep 86400 & wait \"$!\" || true; done\n",
                encoding="utf-8",
            )
            grandchild_script.chmod(0o755)
            runner_script.write_text(
                "#!/usr/bin/env bash\n"
                "child_pid=\"\"\n"
                "shutdown() {\n"
                "  printf term > \"$CHILD_SIGNAL_FILE\"\n"
                "  if [[ -n \"$child_pid\" ]]; then wait \"$child_pid\" 2>/dev/null || true; fi\n"
                "  exit 0\n"
                "}\n"
                "trap shutdown TERM INT\n"
                "\"$GRANDCHILD_SCRIPT\" &\n"
                "child_pid=$!\n"
                "printf ready > \"$CHILD_READY_FILE\"\n"
                "wait \"$child_pid\"\n",
                encoding="utf-8",
            )
            runner_script.chmod(0o755)
            python_script.write_text(
                "#!/usr/bin/env bash\n"
                "case \"${2:-}\" in\n"
                "  \\{*) printf '1\\n' ;;\n"
                "  *) printf '{\"market\":\"KOSPI\",\"open\":true}\\n' ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            python_script.chmod(0o755)

            env = {
                **os.environ,
                "CHILD_READY_FILE": str(ready_path),
                "CHILD_SIGNAL_FILE": str(signal_path),
                "GRANDCHILD_SCRIPT": str(grandchild_script),
                "GRANDCHILD_READY_FILE": str(grandchild_ready_path),
                "GRANDCHILD_SIGNAL_FILE": str(grandchild_signal_path),
                "LOGS_DIR": str(temp_path / "logs"),
                "WEALTHPULSE_PYTHON_BIN": str(python_script),
                "WEALTHPULSE_REPO_DIR": str(temp_path),
                "WEALTHPULSE_RESEARCH_LOOP_INTERVAL_SECONDS": "60",
            }
            process = subprocess.Popen(
                [str(loop_script)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )

            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and not (
                    ready_path.exists() and grandchild_ready_path.exists()
                ):
                    time.sleep(0.05)
                self.assertTrue(ready_path.exists())
                self.assertTrue(grandchild_ready_path.exists())

                started_at = time.monotonic()
                process.terminate()
                process.wait(timeout=3)
                elapsed = time.monotonic() - started_at

                self.assertEqual(process.returncode, 0)
                self.assertTrue(signal_path.exists())
                self.assertEqual(signal_path.read_text(encoding="utf-8"), "term")
                self.assertTrue(grandchild_signal_path.exists())
                self.assertEqual(grandchild_signal_path.read_text(encoding="utf-8"), "term")
                self.assertLess(elapsed, 2)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
