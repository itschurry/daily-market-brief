from __future__ import annotations

from routes.hanna import handle_hanna_brief
from routes.reports import handle_reports
from services.strategy_engine import build_signal_book


def handle_reports_explain(date: str | None = None) -> tuple[int, dict]:
    try:
        status, brief = handle_hanna_brief(date)
        if status != 200:
            return status, brief

        analysis = brief.get("analysis") if isinstance(brief, dict) and isinstance(brief.get("analysis"), dict) else {}
        signal_book = build_signal_book(markets=["KOSPI", "NASDAQ"], cfg={})
        return 200, {
            "ok": True,
            "owner": brief.get("owner") if isinstance(brief, dict) else "hanna",
            "brief_type": brief.get("brief_type") if isinstance(brief, dict) else "hanna_operator_brief_v1",
            "migration": brief.get("migration") if isinstance(brief, dict) else {"backend_owner": "hanna"},
            "brief": brief,
            "analysis": analysis,
            "summary_lines": brief.get("summary_lines") if isinstance(brief, dict) else [],
            "signal_reasoning": [
                {
                    "code": item.get("code"),
                    "strategy_type": item.get("strategy_type"),
                    "entry_allowed": item.get("entry_allowed"),
                    "reason_codes": item.get("reason_codes"),
                    "signal_reasoning": item.get("signal_reasoning"),
                }
                for item in signal_book.get("signals", [])[:30]
            ],
            "report_reasoning": brief.get("report_reasoning") if isinstance(brief, dict) else (analysis.get("hanna_context") if isinstance(analysis, dict) else {}),
            "generated_at": (brief.get("generated_at") if isinstance(brief, dict) else None) or signal_book.get("generated_at"),
        }
    except Exception as exc:
        return 500, {"ok": False, "error": str(exc)}


def handle_reports_index() -> tuple[int, dict]:
    return handle_reports()
