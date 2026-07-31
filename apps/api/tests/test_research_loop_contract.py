import pathlib
import re
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


class ResearchLoopContractTest(unittest.TestCase):
    def test_compose_does_not_restart_failed_research_loop(self) -> None:
        compose_path = REPO_ROOT / "docker-compose.yml"
        if not compose_path.exists():
            self.skipTest("docker-compose.yml is not packaged in the API image")

        compose = compose_path.read_text(encoding="utf-8")

        service = re.search(
            r"(?ms)^  research-loop:\n(?P<body>.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
            compose,
        )

        self.assertIsNotNone(service)
        self.assertRegex(service.group("body"), r'(?m)^    restart: "no"$')


if __name__ == "__main__":
    unittest.main()
