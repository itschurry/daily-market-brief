from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


_ALLOWED_WARNING_CODES = {
    "headline_stronger_than_body",
    "already_extended_intraday",
    "low_evidence_density",
    "theme_recycled",
    "contrarian_flow_risk",
    "policy_uncertainty",
    "liquidity_mismatch",
    "too_many_similar_news",
    "research_unavailable",
}


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
        )


class HannaResearchScorer:
    def __init__(self, *, endpoint: str, timeout_seconds: float = 1.5, retry_count: int = 1) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.retry_count = max(0, retry_count)
        self._cache: dict[str, tuple[float, ResearchScoreResult]] = {}

    def score(self, request: ResearchScoreRequest) -> ResearchScoreResult:
        cache_key = self._cache_key(request)
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and cached[0] > now:
            return cached[1]

        payload = {
            "symbol": request.symbol,
            "market": request.market,
            "timestamp": request.timestamp,
            "context": request.context,
        }
        last_error = ""
        for attempt in range(self.retry_count + 1):
            try:
                raw = self._post_json(payload)
                result = self._validate_response(raw, request)
                self._cache[cache_key] = (now + max(60, result.ttl_minutes * 60), result)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt >= self.retry_count:
                    break
        return ResearchScoreResult(
            symbol=request.symbol,
            market=request.market,
            research_score=None,
            components={},
            warnings=["research_unavailable"],
            tags=[],
            summary="Hanna research 응답이 없어 quant+risk 기준으로 계속 진행합니다.",
            ttl_minutes=5,
            generated_at=request.timestamp,
            status="timeout" if "timed out" in last_error.lower() else "degraded",
            source="hanna",
            available=False,
        )

    def _cache_key(self, request: ResearchScoreRequest) -> str:
        bucket = str(request.timestamp)[:16]
        return f"{request.market}:{request.symbol}:{bucket}"

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError("invalid_hanna_payload")
        return parsed

    def _validate_response(self, payload: dict[str, Any], request: ResearchScoreRequest) -> ResearchScoreResult:
        score = payload.get("research_score")
        if score is not None:
            score = max(0.0, min(1.0, float(score)))
        components_raw = payload.get("components") if isinstance(payload.get("components"), dict) else {}
        components = {
            str(key): max(0.0, min(1.0, float(value)))
            for key, value in components_raw.items()
            if isinstance(value, (int, float))
        }
        warnings = [
            str(item) for item in (payload.get("warnings") or [])
            if str(item) in _ALLOWED_WARNING_CODES
        ]
        tags = [str(item) for item in (payload.get("tags") or []) if str(item).strip()]
        ttl_minutes = max(1, min(240, int(payload.get("ttl_minutes") or 60)))
        generated_at = str(payload.get("generated_at") or request.timestamp)
        return ResearchScoreResult(
            symbol=request.symbol,
            market=request.market,
            research_score=score,
            components=components,
            warnings=warnings,
            tags=tags,
            summary=str(payload.get("summary") or ""),
            ttl_minutes=ttl_minutes,
            generated_at=generated_at,
            status="healthy",
            source="hanna",
            available=True,
        )


_SCORER_CACHE_KEY: tuple[str, float, int] | None = None
_SCORER_INSTANCE: ResearchScorer | None = None


def get_research_scorer() -> ResearchScorer:
    global _SCORER_CACHE_KEY, _SCORER_INSTANCE

    endpoint = str(os.getenv("HANNA_RESEARCH_API_URL") or "").strip()
    timeout_seconds = float(os.getenv("HANNA_RESEARCH_TIMEOUT_SECONDS") or 1.5)
    retry_count = int(os.getenv("HANNA_RESEARCH_RETRY_COUNT") or 1)
    cache_key = (endpoint, timeout_seconds, retry_count)

    if _SCORER_INSTANCE is not None and _SCORER_CACHE_KEY == cache_key:
        return _SCORER_INSTANCE

    if not endpoint:
        _SCORER_INSTANCE = NullResearchScorer()
        _SCORER_CACHE_KEY = cache_key
        return _SCORER_INSTANCE

    _SCORER_INSTANCE = HannaResearchScorer(endpoint=endpoint, timeout_seconds=timeout_seconds, retry_count=retry_count)
    _SCORER_CACHE_KEY = cache_key
    return _SCORER_INSTANCE
