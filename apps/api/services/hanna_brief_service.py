from __future__ import annotations

from typing import Any


_ALLOWED_MODE_LABELS = {"낮음": "공격", "중간": "선별", "높음": "축소"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summary_lines_from_analysis(analysis: dict[str, Any]) -> list[str]:
    lines = analysis.get("summary_lines") if isinstance(analysis.get("summary_lines"), list) else []
    normalized = [str(item).strip() for item in lines if str(item).strip()]
    if normalized:
        return normalized[:5]

    summary = str(analysis.get("summary") or analysis.get("brief") or "").strip()
    if summary:
        return [summary]
    return []


def build_hanna_brief_payload(*, analysis: dict[str, Any], date: str | None = None) -> dict[str, Any]:
    summary_lines = _summary_lines_from_analysis(analysis)
    report_reasoning = analysis.get("analysis_playbook") if isinstance(analysis.get("analysis_playbook"), dict) else {}
    generated_at = str(analysis.get("generated_at") or analysis.get("date") or date or "")

    return {
        "ok": True,
        "brief_type": "hanna_operator_brief_v1",
        "owner": "hanna",
        "date": str(analysis.get("date") or date or ""),
        "generated_at": generated_at,
        "summary_lines": summary_lines,
        "analysis": analysis,
        "report_reasoning": report_reasoning,
        "migration": {
            "backend_owner": "hanna",
            "legacy_source_retained": True,
            "stage": "phase_1_bridge",
        },
    }


def build_hanna_brief_from_runtime(
    *,
    signal_book: dict[str, Any],
    market_context: dict[str, Any] | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    market_context = market_context if isinstance(market_context, dict) else {}
    context = market_context.get("context") if isinstance(market_context.get("context"), dict) else {}
    summary = str(
        market_context.get("summary")
        or context.get("summary")
        or context.get("market_view")
        or ""
    ).strip()
    risk_level = str(
        signal_book.get("risk_level")
        or (signal_book.get("risk_guard_state") if isinstance(signal_book.get("risk_guard_state"), dict) else {}).get("risk_level")
        or context.get("risk_level")
        or "중간"
    )
    regime = str(
        signal_book.get("regime")
        or (signal_book.get("risk_guard_state") if isinstance(signal_book.get("risk_guard_state"), dict) else {}).get("regime")
        or context.get("regime")
        or "neutral"
    )
    entry_allowed_count = _to_int(signal_book.get("entry_allowed_count"), 0)
    blocked_count = _to_int(signal_book.get("blocked_count"), 0)
    count = _to_int(signal_book.get("count"), 0)
    stance = _ALLOWED_MODE_LABELS.get(risk_level, "선별")
    guard_state = signal_book.get("risk_guard_state") if isinstance(signal_book.get("risk_guard_state"), dict) else {}
    guard_reasons = [str(item).strip() for item in (guard_state.get("reasons") or []) if str(item).strip()]
    context_risks = [str(item).strip() for item in (market_context.get("risks") or context.get("risks") or []) if str(item).strip()]

    summary_lines: list[str] = []
    if summary:
        summary_lines.append(summary)
    summary_lines.append(f"현재 장세는 {regime}, 위험도는 {risk_level} 기준으로 읽고 있어.")
    summary_lines.append(f"실행 후보 {count}건 중 진입 가능 {entry_allowed_count}건, 차단 {blocked_count}건 상태야.")
    if guard_reasons:
        summary_lines.append(f"리스크 가드 핵심 사유: {guard_reasons[0]}")
    elif blocked_count > 0:
        summary_lines.append("차단 후보는 리스크 가드나 유동성 조건부터 먼저 확인하면 돼.")
    else:
        summary_lines.append("지금은 차단 사유보다 허용 후보 우선순위 정리에 집중하면 돼.")
    if context_risks:
        summary_lines.append(f"시장 주의 포인트: {context_risks[0]}")

    summary_lines = summary_lines[:5]
    generated_at = str(signal_book.get("generated_at") or market_context.get("generated_at") or date or "")
    report_reasoning = {
        "source": "runtime_signal_book",
        "regime": regime,
        "risk_level": risk_level,
        "stance": stance,
        "guard_reasons": guard_reasons[:3],
        "context_risks": context_risks[:3],
    }
    analysis = {
        "date": str(date or market_context.get("date") or ""),
        "generated_at": generated_at,
        "summary_lines": summary_lines,
        "source": "hanna_runtime_brief",
    }

    return {
        "ok": True,
        "brief_type": "hanna_operator_brief_v2",
        "owner": "hanna",
        "date": str(date or market_context.get("date") or ""),
        "generated_at": generated_at,
        "summary_lines": summary_lines,
        "analysis": analysis,
        "report_reasoning": report_reasoning,
        "migration": {
            "backend_owner": "hanna",
            "legacy_source_retained": False,
            "stage": "phase_2_runtime_brief",
        },
    }
