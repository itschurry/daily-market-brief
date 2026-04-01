from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_API_DIR = Path(__file__).resolve().parent.parent
SEARCH_OPTIMIZED_PARAMS_PATH = _API_DIR / "config" / "optimized_params.json"
RUNTIME_OPTIMIZED_PARAMS_PATH = _API_DIR / "config" / "runtime_optimized_params.json"
_EXECUTION_APPROVED_SOURCES = {
    "validated_candidate",
    "quant_ops_saved_candidate",
}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def load_search_optimized_params() -> dict[str, Any] | None:
    return _read_json(SEARCH_OPTIMIZED_PARAMS_PATH)


def load_runtime_optimized_params() -> dict[str, Any] | None:
    return _read_json(RUNTIME_OPTIMIZED_PARAMS_PATH)


def _is_execution_approved_payload(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    source = str(meta.get("global_overlay_source") or "").strip()
    applied_from = str(meta.get("applied_from") or "").strip()
    applied_candidate_id = str(meta.get("applied_candidate_id") or "").strip()
    return bool(
        source in _EXECUTION_APPROVED_SOURCES
        or applied_from in _EXECUTION_APPROVED_SOURCES
        or applied_candidate_id
        or bool(meta.get("execution_approved"))
    )


def load_effective_optimized_params() -> dict[str, Any] | None:
    runtime_payload = load_runtime_optimized_params()
    if runtime_payload:
        return runtime_payload
    return load_search_optimized_params()


def load_execution_optimized_params() -> dict[str, Any] | None:
    runtime_payload = load_runtime_optimized_params()
    if runtime_payload and _is_execution_approved_payload(runtime_payload):
        return runtime_payload

    search_payload = load_search_optimized_params()
    if _is_execution_approved_payload(search_payload):
        return search_payload
    return None


def write_runtime_optimized_params(payload: dict[str, Any]) -> Path:
    RUNTIME_OPTIMIZED_PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_OPTIMIZED_PARAMS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return RUNTIME_OPTIMIZED_PARAMS_PATH


def clear_runtime_optimized_params() -> None:
    try:
        RUNTIME_OPTIMIZED_PARAMS_PATH.unlink(missing_ok=True)
    except Exception:
        pass
