# Design

전북대학교의 학교 사이트를 직접 수집해 신규·수정 공지를 감지하고, 첨부파일의 신청 조건까지 확인하여 사용자의 상황과 목표에 맞는 정보를 Discord 등으로 전달한다. 검색엔진은 발견 보조 수단일 수 있으나 학교 사이트 자체가 source of truth다.

## 상태와 문서 지도

2026-09-21 현재 구현은 **컴퓨터인공지능학부 한 게시판의 목록 fetch/parse**까지다. 아래 흐름은 목표 설계이며 구현 완료를 뜻하지 않는다. 기존 Python 및 Collector/Parser 분리 결정은 유지한다. 단일 게시판의 안정적인 신규 탐지가 첫 milestone이며 그 전에는 AI·다중 출처·자동화 구현을 시작하지 않는다.

- [Repository 조사와 구현 순서](architecture/repository-review.md): 확인한 파일, 현재 한계, 예상 변경 파일, 단계별 완료 조건
- [공지 파이프라인과 저장 모델](architecture/notice-pipeline.md): adapter, 데이터 흐름, archive, 버전/상태와 DB
- [첨부 처리](architecture/attachment-processing.md): 형식 판별, HWP fallback, 품질과 parser 계약
- [개인화 분석](architecture/llm-analysis.md): 규칙/LLM 경계, 사용자 profile, structured output과 우선순위
- [신뢰성과 테스트](architecture/reliability.md): 재시도, 재처리, 알림 멱등성, 회귀 테스트
- [결정 기록](decisions.md): 기존 결정, 이번 설계 원칙, 미결정 선택지

## 목표 흐름

```text
수동 source 등록 → 공통 HTTP Collector + 사이트별 Parser/Adapter
  → 원본 목록/상세 archive + 관측/공지 version
  → 첨부 다운로드/archive → document extraction
  → normalized snapshot → 규칙 전처리
  → LLM structured facts/relevance → 규칙 검증/priority
  → transaction outbox → Discord
```

각 화살표는 같은 Python 프로그램 내 단계다. raw → extracted → normalized → analyzed를 별도 저장하여 parser/prompt가 바뀌어도 원본에서 재처리할 수 있게 한다. 첨부는 독립 상태와 hash를 가진 first-class data다. 수집 실패나 분석 실패는 기존 history를 손상시키지 않으며, 한 단계의 실패로 공지 원본을 버리지 않는다.

발견된 게시물이 목록에서 사라져도 삭제하지 않는다. 신청 가능성·선행조건·근거 완전성을 중요도에 반영하며 J-Point만으로 높은 추천을 확정하지 않는다. 외부 전송의 불확실성을 포함한 notification idempotency 한계는 신뢰성 문서에서 명시한다.
