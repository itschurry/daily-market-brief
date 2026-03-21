"""몬테카를로 최적화 API 엔드포인트."""
from __future__ import annotations

import subprocess
import threading

from api.routes.trading import _load_optimized_params

_optimization_lock = threading.Lock()
_optimization_running = False


def handle_get_optimized_params() -> tuple[int, dict]:
    """GET /api/optimized-params — 최적화 결과 반환."""
    try:
        data = _load_optimized_params()
        if data is None:
            return 200, {"status": "not_optimized", "message": "최적화 미실행 또는 파일 없음"}
        return 200, {"status": "ok", **data}
    except Exception as exc:
        return 500, {"error": str(exc)}


def handle_run_optimization() -> tuple[int, dict]:
    """POST /api/run-optimization — 백그라운드 최적화 실행 트리거."""
    global _optimization_running

    with _optimization_lock:
        if _optimization_running:
            return 200, {"status": "already_running"}
        _optimization_running = True

    def _run() -> None:
        global _optimization_running
        try:
            import sys
            from pathlib import Path
            script = str(Path(__file__).parent.parent.parent / "scripts" / "run_monte_carlo_optimizer.py")
            subprocess.run(
                [sys.executable, script],
                timeout=3600,
                capture_output=False,
            )
        except Exception:
            pass
        finally:
            with _optimization_lock:
                _optimization_running = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return 200, {"status": "started"}
