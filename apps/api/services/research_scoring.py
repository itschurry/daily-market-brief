from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from services.research_contract import normalize_components, normalize_tags, normalize_warning_codes
from services.research_store import DEFAULT_RESEARCH_PROVIDER, load_research_snapshot_for_timestamp


def _parse_datetime(value: Any):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = __import__("datetime").datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=__import__("datetime").timezone.utc)
    return parsed.astimezone(__import__("datetime").timezone.utc)


@dataclass
class ResearchScoreRequest:
    symbol: str
    market: str
    timestamp: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchScoreResult:
    symbol: str
    market: str
    research_score: float | None
    components: dict[str, float]
    warnings: list[str]
    tags: list[str]
    summary: str
    ttl_minutes: int
    generated_at: str
    status: str = "healthy"
    source: str = "null"
    available: bool = True
    freshness: str = "missing"
    freshness_detail: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResearchScorer(Protocol):
    def score(self, request: ResearchScoreRequest) -> ResearchScoreResult:
        ...


class NullResearchScorer:
    def score(self, request: ResearchScoreRequest) -> ResearchScoreResult:
        return ResearchScoreResult(
            symbol=request.symbol,
            market=request.market,
            research_score=None,
            components={},
            warnings=["research_unavailable"],
            tags=[],
            summary="연구 점수 제공자가 설정되지 않아 quant+risk 기준으로 계속 진행합니다.",
            ttl_minutes=5,
            generated_at=request.timestamp,
            status="research_unavailable",
            source="null",
            available=False,
            freshness="missing",
            freshness_detail={"status": "missing", "is_stale": True, "reason": "provider_missing"},
            validation={
                "grade": "D",
                "source": "null",
                "source_count": 0,
                "reason": "provider_missing",
                "notes": ["research_unavailable"],
                "exclusion_reason": "research scorer provider is not configured",
            },
        )


class StoredResearchScorer:
    def __init__(self, *, provider: str = DEFAULT_RESEARCH_PROVIDER) -> None:
        self.provider = str(provider or DEFAULT_RESEARCH_PROVIDER).strip().lower() or DEFAULT_RESEARCH_PROVIDER

    def score(self, request: ResearchScoreRequest) -> ResearchScoreResult:
        snapshot = load_research_snapshot_for_timestamp(request.symbol, request.market, request.timestamp, provider=self.provider)
        if not isinstance(snapshot, dict):
            return ResearchScoreResult(
                symbol=request.symbol,
                market=request.market,
                research_score=None,
                components={},
                warnings=["research_unavailable"],
                tags=[],
                summary="Research snapshot이 없어 quant+risk 기준으로 계속 진행합니다.",
                ttl_minutes=5,
                generated_at=request.timestamp,
                status="missing",
                source=self.provider,
                available=False,
                freshness="missing",
                freshness_detail={"status": "missing", "is_stale": True, "reason": "snapshot_missing"},
                validation={
                    "grade": "D",
                    "source": self.provider,
                    "source_count": 0,
                    "reason": "snapshot_missing",
                    "notes": ["research_unavailable"],
                    "exclusion_reason": "research snapshot not found",
                },
            )

        ttl_minutes = max(1, min(1440, int(snapshot.get("ttl_minutes") or 120)))
        generated_at = str(snapshot.get("generated_at") or request.timestamp)
        generated_dt = _parse_datetime(generated_at)
        reference_dt = _parse_datetime(request.timestamp)
        freshness = snapshot.get("freshness") if isinstance(snapshot.get("freshness"), str) else "missing"
        freshness_detail = snapshot.get("freshness_detail") if isinstance(snapshot.get("freshness_detail"), dict) else {}
        validation = snapshot.get("validation") if isinstance(snapshot.get("validation"), dict) else {}
        if generated_dt is None or reference_dt is None or reference_dt > generated_dt + __import__("datetime").timedelta(minutes=ttl_minutes):
            return ResearchScoreResult(
                symbol=request.symbol,
                market=request.market,
                research_score=None,
                components={},
                warnings=["research_unavailable"],
                tags=[],
                summary="Research snapshot이 오래되어 quant+risk 기준으로 계속 진행합니다.",
                ttl_minutes=ttl_minutes,
                generated_at=generated_at,
                status="stale_ingest",
                source=self.provider,
                available=False,
                freshness="stale",
                freshness_detail=freshness_detail or {"status": "stale", "is_stale": True, "reason": "ttl_expired"},
                validation=validation or {
                    "grade": "C",
                    "source": self.provider,
                    "source_count": 1,
                    "reason": "stale_snapshot",
                    "notes": ["research_unavailable", "ttl_expired"],
                    "exclusion_reason": None,
                },
            )

        return ResearchScoreResult(
            symbol=request.symbol,
            market=request.market,
            research_score=snapshot.get("research_score"),
            components=normalize_components(snapshot.get("components")),
            warnings=normalize_warning_codes(snapshot.get("warnings")),
            tags=normalize_tags(snapshot.get("tags")),
            summary=str(snapshot.get("summary") or ""),
            ttl_minutes=ttl_minutes,
            generated_at=generated_at,
            status="healthy",
            source=self.provider,
            available=True,
            freshness=freshness or "fresh",
            freshness_detail=freshness_detail,
            validation=validation,
        )


_SCORER_CACHE_KEY: str | None = None
_SCORER_INSTANCE: ResearchScorer | None = None


def get_research_scorer() -> ResearchScorer:
    global _SCORER_CACHE_KEY, _SCORER_INSTANCE

    provider = DEFAULT_RESEARCH_PROVIDER
    cache_key = provider

    if _SCORER_INSTANCE is not None and _SCORER_CACHE_KEY == cache_key:
        return _SCORER_INSTANCE

    _SCORER_INSTANCE = StoredResearchScorer(provider=provider)
    _SCORER_CACHE_KEY = cache_key
    return _SCORER_INSTANCE
