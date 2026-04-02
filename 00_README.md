# WealthPulse Layer A~E 구조 전환 + 비퀀트 엔진 제거 + Hanna API 연동 하네스

이 패키지는 WealthPulse를 아래 방향으로 개편하기 위한 작업 지시서다.

## 목표
- 기존 비퀀트 엔진을 전부 제거
- Layer A ~ E 구조로 엔진 재구성
- Hanna Research Score 연동용 API 인터페이스 도입
- Hanna는 엔진 내부 로직이 아니라 외부 scorer 플러그인으로만 연결
- 최종 주문 판단은 Quant + Risk Gate가 담당

## 목표 구조
- Layer A. Universe / Scanner
- Layer B. Quant Strategy Score
- Layer C. Hanna Research Score API
- Layer D. Risk / Execution Gate
- Layer E. Final Action

## 핵심 원칙
- 비퀀트 엔진 전부 제거
- Hanna는 research scorer API로만 붙임
- Hanna API는 주문/매수 명령을 내리지 않음
- Risk Gate가 최종 거부권을 가짐
- 실시간 경로에 백테스트/최적화/검증 재호출 금지

## 문서 구성
- `01_summary.md` : 전체 방향 요약
- `02_target_architecture.md` : Layer A~E 목표 구조
- `03_backend_tasks.md` : 백엔드 구현 지시
- `04_hanna_api_spec.md` : Hanna Research Score API 명세
- `05_ui_tasks.md` : UI 개편 지시
- `06_acceptance_checklist.md` : 완료 기준
- `07_codex_prompt.md` : 코덱스 투입용 프롬프트

## 권장 작업 순서
1. `06_acceptance_checklist.md` 먼저 읽기
2. `02_target_architecture.md` 구조 파악
3. `03_backend_tasks.md`로 백엔드 구조 반영
4. `04_hanna_api_spec.md` 기준으로 API 계약 반영
5. `05_ui_tasks.md` 반영
6. `06_acceptance_checklist.md`로 자체 검수
