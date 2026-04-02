# 06. 완료 기준 체크리스트

## 구조
- [ ] 기존 비퀀트 엔진이 전부 제거되었다
- [ ] Layer A ~ E 구조가 코드와 UI에 반영되었다
- [ ] Layer C는 Hanna API scorer로만 동작한다
- [ ] Layer D가 최종 거부권을 가진다

## 백엔드
- [ ] ResearchScorer 인터페이스가 도입되었다
- [ ] NullResearchScorer와 HannaResearchScorer가 존재한다
- [ ] Hanna API timeout/retry/fallback 정책이 구현되었다
- [ ] free-form text가 아니라 구조화된 DTO로만 Layer C가 동작한다
- [ ] Final Action snapshot이 `review_for_entry / watch_only / blocked / do_not_touch` 중 하나로 기록된다
- [ ] Final Action snapshot에는 timestamp와 source context가 함께 남는다
- [ ] layer별 이벤트 로그가 남는다

## UI
- [ ] 후보 상세 화면에서 Layer A~E 판단 근거를 볼 수 있다
- [ ] 실시간 스캐너 화면에 quant_score / research_score / final_action이 표시된다
- [ ] Risk / Action 로그 화면에서 reason code를 볼 수 있다
- [ ] Hanna 상태 배지가 있다
- [ ] legacy 비퀀트 관련 UI가 제거되었다

## 회귀 방지
- [ ] Hanna API가 직접 주문하지 않는다
- [ ] Hanna 응답의 action/confidence를 그대로 사용하지 않는다
- [ ] 기존 추천 엔진/뉴스 엔진/테마 엔진 잔재가 주문 경로에 남아 있지 않다
- [ ] Layer C가 Layer D를 우회하지 않는다
- [ ] 실시간 경로에서 백테스트/최적화/검증 재호출이 없다
- [ ] Layer A는 주문 판단을 하지 않는다
- [ ] Layer B는 리스크 veto를 수행하지 않는다
- [ ] Layer C는 주문/action을 직접 결정하지 않는다
- [ ] Layer D는 research summary를 생성하지 않는다
- [ ] Layer E는 원본 layer output을 덮어쓰지 않고 결론 snapshot만 기록한다
