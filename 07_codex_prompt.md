# 07. Codex 투입용 프롬프트

작업 디렉토리의 md 문서를 모두 읽고 작업해.

반드시 `06_acceptance_checklist.md`를 먼저 읽어서 완료 기준을 파악한 뒤,
`02_target_architecture.md`, `03_backend_tasks.md`, `04_hanna_api_spec.md`, `05_ui_tasks.md`
순서로 반영해.

목표는 다음과 같다.

1. 기존 비퀀트 엔진 전부 제거
2. WealthPulse를 Layer A ~ E 구조로 재구성
3. Hanna를 내부 엔진이 아닌 외부 Research Score API로 연결
4. Layer D Risk / Execution Gate가 최종 거부권 유지
5. UI에서 Layer A~E 판단 근거를 드러내기

반드시 아래 원칙을 지켜:
- Hanna API는 주문/매수 명령을 내리지 않는다
- free-form text 파싱 기반 의사결정 금지
- 구조화된 score / warnings / tags / ttl 기반으로만 연동
- legacy 비퀀트 엔진/추천 엔진/뉴스 엔진 잔재 제거
- Final Action snapshot을 명시적으로 기록/표시
- Layer C는 review 우선순위와 경고를 보조할 뿐, Layer D를 우회하지 않는다
- research timeout 시 live 경로를 멈추지 말고 `research_unavailable` 상태로 계속 진행한다

작업 후에는 `06_acceptance_checklist.md` 기준 자체 점검 결과를 함께 남겨.
