from __future__ import annotations

import sys
import unittest
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from scripts.openai_research_runner import _runner_exit_code


class OpenAIResearchRunnerExitTests(unittest.TestCase):
    def test_partial_quality_rejections_keep_loop_running(self) -> None:
        self.assertEqual(
            _runner_exit_code(207, {
                "partial_failure": True,
                "agent_success_count": 6,
                "agent_error_count": 2,
                "quality_rejection_count": 2,
                "system_failure_count": 0,
            }),
            0,
        )

    def test_partial_system_failure_stops_loop(self) -> None:
        self.assertEqual(
            _runner_exit_code(207, {
                "partial_failure": True,
                "agent_success_count": 6,
                "agent_error_count": 2,
                "quality_rejection_count": 1,
                "system_failure_count": 1,
            }),
            2,
        )

    def test_all_targets_rejected_keep_loop_running(self) -> None:
        self.assertEqual(
            _runner_exit_code(200, {
                "agent_success_count": 0,
                "agent_error_count": 8,
                "quality_rejection_count": 8,
                "system_failure_count": 0,
            }),
            0,
        )

    def test_all_targets_system_failure_stops_loop(self) -> None:
        self.assertEqual(
            _runner_exit_code(502, {
                "agent_success_count": 0,
                "agent_error_count": 8,
                "quality_rejection_count": 0,
                "system_failure_count": 8,
            }),
            1,
        )


if __name__ == "__main__":
    unittest.main()
