from __future__ import annotations

import copy
import datetime as dt
import json
import uuid
from pathlib import Path
from typing import Any

from config.settings import LOGS_DIR
from services.optimized_params_store import (
    RUNTIME_OPTIMIZED_PARAMS_PATH,
    SEARCH_OPTIMIZED_PARAMS_PATH,
    load_runtime_optimized_params,
    load_search_optimized_params,
    write_runtime_optimized_params,
)
from services.validation_service import run_validation_diagnostics


_QUANT_OPS_STATE_PATH = LOGS_DIR / "quant_ops_state.json"
_OPTIMIZABLE_KEYS = {
    "stop_loss_pct",
    "take_profit_pct",
    "max_holding_days",
    "rsi_min",
    "rsi_max",
    "volume_ratio_min",
    "adx_min",
    "mfi_min",
    "mfi_max",
    "bb_pct_min",
    "bb_pct_max",
    "stoch_k_min",
    "stoch_k_max",
}
_OPTIMIZED_PARAMS_MAX_AGE_DAYS = 30


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else dict(default)
    except Exception:
        return dict(default)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state() -> dict[str, Any]:
    return _read_json(
        _QUANT_OPS_STATE_PATH,
        {
            "latest_candidate": None,
            "candidate_history": [],
            "saved_candidate": None,
            "saved_history": [],
            "runtime_apply": None,
        },
    )


def _save_state(state: dict[str, Any]) -> None:
    _write_json(_QUANT_OPS_STATE_PATH, state)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_stale(optimized_at: str) -> bool:
    if not optimized_at:
        return False
    try:
        optimized_ts = dt.datetime.fromisoformat(optimized_at)
        age_days = (dt.datetime.now(dt.timezone.utc) - optimized_ts.astimezone(dt.timezone.utc)).days
        return age_days > _OPTIMIZED_PARAMS_MAX_AGE_DAYS
    except Exception:
        return True


def _search_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    global_params = payload.get("global_params") if isinstance(payload.get("global_params"), dict) else {}
    per_symbol = payload.get("per_symbol") if isinstance(payload.get("per_symbol"), dict) else {}
    optimized_at = str(payload.get("optimized_at") or "")
    return {
        "available": bool(payload),
        "version": str(payload.get("version") or optimized_at or "not_optimized"),
        "optimized_at": optimized_at,
        "is_stale": _is_stale(optimized_at),
        "global_params": global_params,
        "param_count": len(global_params),
        "per_symbol_count": len(per_symbol),
        "n_symbols_optimized": _to_int(meta.get("n_symbols_optimized"), len(per_symbol)),
        "n_reliable": _to_int(meta.get("n_reliable"), 0),
        "n_medium": _to_int(meta.get("n_medium"), 0),
        "global_overlay_source": meta.get("global_overlay_source"),
        "source": str(SEARCH_OPTIMIZED_PARAMS_PATH),
    }


def _build_service_query(query: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, list[str]]:
    service_query: dict[str, list[str]] = {}
    for key, value in (query or {}).items():
        if value is None or value == "":
            continue
        service_query[str(key)] = [str(value)]
    settings = settings or {}
    if settings:
        mapping = {
            "trainingDays": "training_days",
            "validationDays": "validation_days",
            "walkForward": "walk_forward",
            "minTrades": "validation_min_trades",
            "objective": "objective",
        }
        for raw_key, value in settings.items():
            if value is None or value == "":
                continue
            key = mapping.get(raw_key, raw_key)
            if raw_key == "walkForward":
                service_query[key] = ["true" if bool(value) else "false"]
            else:
                service_query[key] = [str(value)]
    return service_query


def _merge_query_patch(query: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(query or {})
    for key, value in (patch or {}).items():
        if key not in _OPTIMIZABLE_KEYS:
            continue
        merged[key] = value
    return merged


def _patch_lines(base_query: dict[str, Any], mutated_query: dict[str, Any], patch: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in sorted(patch.keys()):
        before = base_query.get(key)
        after = mutated_query.get(key)
        if before == after:
            continue
        lines.append(f"{key}: {before} → {after}")
    return lines


def _read_validation_metrics(validation_payload: dict[str, Any]) -> dict[str, Any]:
    segments = validation_payload.get("segments") if isinstance(validation_payload.get("segments"), dict) else {}
    summary = validation_payload.get("summary") if isinstance(validation_payload.get("summary"), dict) else {}
    oos = segments.get("oos") if isinstance(segments.get("oos"), dict) else {}
    scorecard = validation_payload.get("scorecard") if isinstance(validation_payload.get("scorecard"), dict) else {}
    if not scorecard and isinstance(oos.get("strategy_scorecard"), dict):
        scorecard = oos.get("strategy_scorecard")
    tail_risk = scorecard.get("tail_risk") if isinstance(scorecard.get("tail_risk"), dict) else {}
    reliability_diagnostic = summary.get("reliability_diagnostic") if isinstance(summary.get("reliability_diagnostic"), dict) else {}
    return {
        "oos_return_pct": round(_to_float(oos.get("total_return_pct"), 0.0), 4),
        "profit_factor": round(_to_float(oos.get("profit_factor"), 0.0), 4),
        "max_drawdown_pct": round(_to_float(oos.get("max_drawdown_pct"), 0.0), 4),
        "trade_count": _to_int(oos.get("trade_count"), 0),
        "win_rate_pct": round(_to_float(oos.get("win_rate_pct"), 0.0), 4),
        "positive_window_ratio": round(_to_float(summary.get("positive_window_ratio"), 0.0), 4),
        "windows": _to_int(summary.get("windows"), 0),
        "reliability": str(summary.get("oos_reliability") or "insufficient"),
        "composite_score": round(_to_float(scorecard.get("composite_score"), 0.0), 4),
        "expected_shortfall_5_pct": round(_to_float(tail_risk.get("expected_shortfall_5_pct"), 0.0), 4),
        "return_p05_pct": round(_to_float(tail_risk.get("return_p05_pct"), 0.0), 4),
        "reliability_target_reached": bool(reliability_diagnostic.get("target_reached")),
    }


def _candidate_decision(metrics: dict[str, Any], *, min_trades: int, search_is_stale: bool, search_version_changed: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    oos_return = _to_float(metrics.get("oos_return_pct"), 0.0)
    profit_factor = _to_float(metrics.get("profit_factor"), 0.0)
    max_drawdown_pct = _to_float(metrics.get("max_drawdown_pct"), 0.0)
    trade_count = _to_int(metrics.get("trade_count"), 0)
    reliability = str(metrics.get("reliability") or "insufficient")
    positive_window_ratio = _to_float(metrics.get("positive_window_ratio"), 0.0)
    expected_shortfall = _to_float(metrics.get("expected_shortfall_5_pct"), 0.0)

    decision_status = "hold"
    decision_label = "보류"
    summary = "재검증은 끝났지만 아직 저장/런타임 반영까지 가기엔 근거가 부족합니다."

    hard_reasons: list[str] = []
    if trade_count < max(1, min_trades):
        hard_reasons.append("validation_min_trades_not_met")
    if reliability in {"low", "insufficient"}:
        hard_reasons.append("oos_reliability_low")
    if profit_factor < 0.95:
        hard_reasons.append("profit_factor_too_low")
    if oos_return < -2.0:
        hard_reasons.append("oos_return_negative")
    if abs(max_drawdown_pct) > 30.0:
        hard_reasons.append("max_drawdown_too_large")
    if expected_shortfall < -20.0:
        hard_reasons.append("tail_risk_too_large")

    if not hard_reasons:
        if (
            oos_return > 0.0
            and reliability == "high"
            and profit_factor >= 1.1
            and abs(max_drawdown_pct) <= 20.0
            and trade_count >= max(1, min_trades)
            and positive_window_ratio >= 0.5
            and expected_shortfall >= -14.0
        ):
            decision_status = "adopt"
            decision_label = "채택 후보"
            summary = "OOS·신뢰도·표본·테일리스크 조건을 모두 통과해서 저장 후보로 승격할 수 있습니다."
        else:
            decision_status = "hold"
            decision_label = "보류"
            summary = "핵심 위험은 치명적이지 않지만 채택 조건을 아직 충분히 넘지 못했습니다."
    else:
        decision_status = "reject"
        decision_label = "거절"
        summary = "현재 후보는 재검증 조건을 넘지 못해서 저장/반영을 막습니다."

    guardrail_reasons = list(hard_reasons)
    if search_is_stale:
        guardrail_reasons.append("optimizer_search_stale")
    if search_version_changed:
        guardrail_reasons.append("optimizer_search_version_changed")

    can_save = decision_status == "adopt" and not search_is_stale and not search_version_changed
    can_apply = can_save
    if not can_save and decision_status == "adopt" and search_is_stale:
        summary = "재검증은 통과했지만 optimizer 결과가 오래돼서 저장을 막습니다. 먼저 후보 탐색을 다시 실행하세요."
    if not can_save and decision_status == "adopt" and search_version_changed:
        summary = "재검증한 optimizer 버전과 현재 탐색 결과가 달라져서 저장을 막습니다. 다시 재검증해야 합니다."

    return {
        "status": decision_status,
        "label": decision_label,
        "summary": summary,
        "hard_reasons": hard_reasons,
    }, {
        "can_save": can_save,
        "can_apply": can_apply,
        "reasons": guardrail_reasons,
    }


def _refresh_candidate(candidate: dict[str, Any] | None, search: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    refreshed = copy.deepcopy(candidate)
    metrics = refreshed.get("metrics") if isinstance(refreshed.get("metrics"), dict) else {}
    settings = refreshed.get("settings") if isinstance(refreshed.get("settings"), dict) else {}
    min_trades = _to_int(settings.get("minTrades"), 8)
    search_version_changed = bool(search.get("available")) and str(refreshed.get("search_version") or "") != str(search.get("version") or "")
    decision, guardrails = _candidate_decision(
        metrics,
        min_trades=min_trades,
        search_is_stale=bool(search.get("is_stale")),
        search_version_changed=search_version_changed,
    )
    refreshed["decision"] = decision
    refreshed["guardrails"] = guardrails
    return refreshed


def _build_candidate(
    *,
    search: dict[str, Any],
    base_query: dict[str, Any],
    mutated_query: dict[str, Any],
    settings: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    validation = diagnostics.get("validation") if isinstance(diagnostics.get("validation"), dict) else {}
    diagnosis = diagnostics.get("diagnosis") if isinstance(diagnostics.get("diagnosis"), dict) else {}
    research = diagnostics.get("research") if isinstance(diagnostics.get("research"), dict) else {}
    metrics = _read_validation_metrics(validation)
    patch = {key: value for key, value in (search.get("global_params") or {}).items() if key in _OPTIMIZABLE_KEYS}
    search_version_changed = False
    decision, guardrails = _candidate_decision(
        metrics,
        min_trades=_to_int(settings.get("minTrades"), 8),
        search_is_stale=bool(search.get("is_stale")),
        search_version_changed=search_version_changed,
    )
    return {
        "id": f"cand-{uuid.uuid4().hex[:12]}",
        "created_at": _now_iso(),
        "source": "optimizer_global_overlay",
        "strategy_label": str(settings.get("strategy") or "퀀트 전략 엔진"),
        "search_version": str(search.get("version") or ""),
        "search_optimized_at": str(search.get("optimized_at") or ""),
        "search_is_stale": bool(search.get("is_stale")),
        "base_query": base_query,
        "candidate_query": mutated_query,
        "settings": settings,
        "patch": patch,
        "patch_lines": _patch_lines(base_query, mutated_query, patch),
        "metrics": metrics,
        "decision": decision,
        "guardrails": guardrails,
        "diagnosis": diagnosis,
        "research": research,
        "validation": validation,
    }


def _history_push(items: list[dict[str, Any]], candidate: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    candidate_id = str(candidate.get("id") or "")
    deduped = [item for item in items if str(item.get("id") or "") != candidate_id]
    return [candidate, *deduped][:limit]


def _runtime_summary(runtime_payload: dict[str, Any] | None, state_runtime: dict[str, Any] | None) -> dict[str, Any]:
    runtime_payload = runtime_payload or {}
    state_runtime = state_runtime if isinstance(state_runtime, dict) else {}
    meta = runtime_payload.get("meta") if isinstance(runtime_payload.get("meta"), dict) else {}
    return {
        "available": bool(runtime_payload),
        "status": "applied" if runtime_payload else "missing",
        "candidate_id": str(meta.get("applied_candidate_id") or state_runtime.get("candidate_id") or ""),
        "applied_at": str(runtime_payload.get("applied_at") or state_runtime.get("applied_at") or ""),
        "version": str(runtime_payload.get("version") or runtime_payload.get("optimized_at") or ""),
        "effective_source": "runtime" if runtime_payload else "search",
        "source": str(RUNTIME_OPTIMIZED_PARAMS_PATH),
        "engine_state": state_runtime.get("engine_state"),
        "next_run_at": state_runtime.get("next_run_at"),
    }


def get_quant_ops_workflow() -> dict[str, Any]:
    state = _load_state()
    search = _search_summary(load_search_optimized_params())
    latest_candidate = _refresh_candidate(state.get("latest_candidate"), search)
    saved_candidate = _refresh_candidate(state.get("saved_candidate"), search)
    runtime_apply = _runtime_summary(load_runtime_optimized_params(), state.get("runtime_apply"))

    stage_status = {
        "candidate_search": "ready" if search.get("available") else "missing",
        "revalidation": str(((latest_candidate or {}).get("decision") or {}).get("status") or "missing"),
        "save": "saved" if saved_candidate else "missing",
        "runtime_apply": str(runtime_apply.get("status") or "missing"),
    }

    return {
        "ok": True,
        "search_result": search,
        "latest_candidate": latest_candidate,
        "saved_candidate": saved_candidate,
        "runtime_apply": runtime_apply,
        "stage_status": stage_status,
        "notes": [
            "optimizer 결과는 후보 탐색용이고, latest_candidate는 재검증이 끝난 운영 후보입니다.",
            "saved_candidate는 재검증 통과 후 저장된 스냅샷이고, runtime_apply는 실제 런타임에 적용된 상태입니다.",
        ],
    }


def revalidate_optimizer_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    query = payload.get("query") if isinstance(payload.get("query"), dict) else {}
    settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else {}
    search = _search_summary(load_search_optimized_params())
    if not search.get("available"):
        return {"ok": False, "error": "optimizer_search_missing", "workflow": get_quant_ops_workflow()}
    if not search.get("global_params"):
        return {"ok": False, "error": "optimizer_global_params_missing", "workflow": get_quant_ops_workflow()}

    mutated_query = _merge_query_patch(query, search.get("global_params") or {})
    diagnostics = run_validation_diagnostics(_build_service_query(mutated_query, settings))
    if not isinstance(diagnostics, dict) or diagnostics.get("error") or not diagnostics.get("ok"):
        return {
            "ok": False,
            "error": str((diagnostics or {}).get("error") or "candidate_revalidation_failed"),
            "details": diagnostics,
            "workflow": get_quant_ops_workflow(),
        }

    candidate = _build_candidate(
        search=search,
        base_query=query,
        mutated_query=mutated_query,
        settings=settings,
        diagnostics=diagnostics,
    )
    state = _load_state()
    state["latest_candidate"] = candidate
    state["candidate_history"] = _history_push(
        state.get("candidate_history") if isinstance(state.get("candidate_history"), list) else [],
        candidate,
    )
    _save_state(state)
    return {
        "ok": True,
        "candidate": candidate,
        "workflow": get_quant_ops_workflow(),
    }


def _resolve_candidate_for_save(candidate_id: str | None = None) -> dict[str, Any] | None:
    state = _load_state()
    latest = state.get("latest_candidate") if isinstance(state.get("latest_candidate"), dict) else None
    if not candidate_id:
        return latest
    if latest and str(latest.get("id") or "") == candidate_id:
        return latest
    history = state.get("candidate_history") if isinstance(state.get("candidate_history"), list) else []
    for item in history:
        if isinstance(item, dict) and str(item.get("id") or "") == candidate_id:
            return item
    return None


def save_validated_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(payload.get("candidate_id") or "").strip() or None
    note = str(payload.get("note") or "").strip()
    search = _search_summary(load_search_optimized_params())
    candidate = _refresh_candidate(_resolve_candidate_for_save(candidate_id), search)
    if not candidate:
        return {"ok": False, "error": "validated_candidate_missing", "workflow": get_quant_ops_workflow()}
    guardrails = candidate.get("guardrails") if isinstance(candidate.get("guardrails"), dict) else {}
    if not bool(guardrails.get("can_save")):
        return {
            "ok": False,
            "error": "save_guardrail_blocked",
            "candidate": candidate,
            "workflow": get_quant_ops_workflow(),
        }

    saved_candidate = {
        **candidate,
        "saved_at": _now_iso(),
        "save_note": note,
    }
    state = _load_state()
    state["saved_candidate"] = saved_candidate
    state["saved_history"] = _history_push(
        state.get("saved_history") if isinstance(state.get("saved_history"), list) else [],
        saved_candidate,
    )
    _save_state(state)
    return {
        "ok": True,
        "candidate": saved_candidate,
        "workflow": get_quant_ops_workflow(),
    }


def _build_runtime_payload(candidate: dict[str, Any], search_payload: dict[str, Any] | None) -> dict[str, Any]:
    search_payload = search_payload or {}
    meta = search_payload.get("meta") if isinstance(search_payload.get("meta"), dict) else {}
    applied_at = _now_iso()
    return {
        "optimized_at": applied_at,
        "applied_at": applied_at,
        "version": f"runtime-{candidate.get('id')}",
        "global_params": dict(candidate.get("patch") or {}),
        "per_symbol": dict(search_payload.get("per_symbol") or {}),
        "meta": {
            **meta,
            "applied_candidate_id": candidate.get("id"),
            "applied_candidate_saved_at": candidate.get("saved_at"),
            "applied_from": "quant_ops_saved_candidate",
            "search_version": candidate.get("search_version"),
            "search_optimized_at": candidate.get("search_optimized_at"),
            "global_overlay_source": "validated_candidate",
        },
    }


def apply_saved_candidate_to_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(payload.get("candidate_id") or "").strip() or None
    state = _load_state()
    raw_saved = state.get("saved_candidate") if isinstance(state.get("saved_candidate"), dict) else None
    if candidate_id and raw_saved and str(raw_saved.get("id") or "") != candidate_id:
        history = state.get("saved_history") if isinstance(state.get("saved_history"), list) else []
        raw_saved = next((item for item in history if isinstance(item, dict) and str(item.get("id") or "") == candidate_id), None)
    search = _search_summary(load_search_optimized_params())
    saved_candidate = _refresh_candidate(raw_saved, search)
    if not saved_candidate:
        return {"ok": False, "error": "saved_candidate_missing", "workflow": get_quant_ops_workflow()}
    guardrails = saved_candidate.get("guardrails") if isinstance(saved_candidate.get("guardrails"), dict) else {}
    if not bool(guardrails.get("can_apply")):
        return {
            "ok": False,
            "error": "runtime_apply_guardrail_blocked",
            "candidate": saved_candidate,
            "workflow": get_quant_ops_workflow(),
        }

    runtime_payload = _build_runtime_payload(saved_candidate, load_search_optimized_params())
    write_runtime_optimized_params(runtime_payload)

    engine_state_payload: dict[str, Any] = {}
    try:
        from services.execution_service import apply_quant_candidate_runtime_config

        engine_state_payload = apply_quant_candidate_runtime_config(saved_candidate)
    except Exception as exc:  # pragma: no cover - defensive route handling
        engine_state_payload = {"ok": False, "error": str(exc)}

    runtime_apply = {
        "candidate_id": saved_candidate.get("id"),
        "applied_at": runtime_payload.get("applied_at"),
        "engine_state": ((engine_state_payload.get("state") or {}).get("engine_state") if isinstance(engine_state_payload.get("state"), dict) else None),
        "next_run_at": ((engine_state_payload.get("state") or {}).get("next_run_at") if isinstance(engine_state_payload.get("state"), dict) else None),
    }
    saved_candidate = {
        **saved_candidate,
        "applied_at": runtime_payload.get("applied_at"),
    }
    state["saved_candidate"] = saved_candidate
    state["runtime_apply"] = runtime_apply
    _save_state(state)
    return {
        "ok": True,
        "candidate": saved_candidate,
        "runtime_apply": runtime_apply,
        "engine": engine_state_payload,
        "workflow": get_quant_ops_workflow(),
    }
