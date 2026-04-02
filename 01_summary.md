# 01. 요약 지시서

## 현재 문제
기존 구조에는 비퀀트 추천/뉴스/테마 판단 로직이 엔진 내부에 직접 섞여 있거나,
과거 구조와 잔재가 남아 있을 가능성이 높다.

이 상태는 아래 문제가 있다.

- 책임 경계가 흐려짐
- 유지보수가 어려움
- 비퀀트 로직이 주문 경로를 오염시킴
- 추천 로직 교체가 어려움
- 리스크 게이트보다 추천 로직이 앞서는 위험한 구조가 됨

## 이번 개편의 목적
1. 기존 비퀀트 엔진을 전부 제거한다
2. 엔진을 Layer A ~ E 구조로 재구성한다
3. Hanna는 내부 엔진이 아니라 외부 API scorer로만 붙인다
4. 최종 주문 권한은 항상 Risk / Execution Gate가 쥔다
5. UI에서 quant / hanna / risk / action 상태를 분리해서 보여준다

## 목표 레이어
```text
Layer A. Universe / Scanner
Layer B. Quant Strategy Score
Layer C. Hanna Research Score API
Layer D. Risk / Execution Gate
Layer E. Final Action
```

## 한 줄 정의
엔진은 시장 스캔 결과를 노출하고, Hanna는 이슈 해석과 경고를 붙이고, Risk Gate가 최종으로 자른다.

## 반드시 하지 말 것
- Hanna API가 직접 주문 호출
- Hanna 응답의 buy/sell 명령을 그대로 실행
- confidence 하나만 받아서 매매 판단
- 기존 비퀀트 엔진 잔재를 adapter 없이 계속 유지
- Layer C가 Layer D를 우회
