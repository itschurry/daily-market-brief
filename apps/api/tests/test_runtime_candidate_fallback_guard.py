from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import signal_service as svc


class RuntimeCandidateFallbackGuardTests(unittest.TestCase):
    def test_runtime_collection_disables_recommendation_fallback_by_default(self):
        with patch.object(svc, "_get_today_picks", return_value={"auto_candidates": []}), \
             patch.object(
                 svc,
                 "_get_recommendations",
                 return_value={
                     "recommendations": [
                         {
                             "ticker": "AAPL",
                             "market": "NASDAQ",
                             "signal": "buy",
                             "score": 77,
                         }
                     ]
                 },
             ):
            candidates = svc.collect_pick_candidates("NASDAQ", cfg={})

        self.assertEqual([], candidates)

    def test_runtime_collection_returns_empty_when_no_quant_params(self):
        # research_only 모드 제거 후 quant 파라미터 없으면 항상 빈 목록 반환
        # live scanner fallback은 strategy_engine.build_signal_book() 계층에서 처리
        with patch.object(svc, "load_execution_optimized_params", return_value=None), \
             patch.object(svc, "_get_today_picks", return_value={"auto_candidates": []}), \
             patch.object(
                 svc,
                 "_get_recommendations",
                 return_value={
                     "recommendations": [
                         {
                             "ticker": "AAPL",
                             "market": "NASDAQ",
                             "signal": "buy",
                             "score": 77,
                         }
                     ]
                 },
             ):
            candidates = svc.collect_pick_candidates(
                "NASDAQ",
                cfg={"allow_recommendation_fallback": True},
            )

        self.assertEqual([], candidates)


if __name__ == "__main__":
    unittest.main()
