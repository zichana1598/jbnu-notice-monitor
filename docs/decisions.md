# Decisions

설계 과정에서 내린 결정과 이유를 기록한다. 현재 시스템 구조는 [design.md](design.md)에 정리한다.

## 2026-09-15 — Collector와 Parser 분리

Collector는 원본 데이터 수집을, Parser는 수집한 데이터를 Notice로 변환하는 일을 맡는다. 하나의 컴포넌트에서 둘 다 처리하면 네트워크 통신과 데이터 해석이 결합되므로 분리한다. 이를 통해 Parser를 독립적으로 테스트하거나 교체할 수 있다.

사이트별 Collector가 필요한지는 아직 정하지 않았다. 단순한 HTTP 요청으로 동일하게 데이터를 가져올 수 있다면 공통 Collector를 쓰고 Parser만 사이트별로 분리할 수 있다.

## 2026-09-15 — Python 사용

구현 언어는 Python으로 정했다. 핵심 작업이 웹 데이터 수집, HTML 파싱, 분류, 자동화이고, 현재 별도의 웹 애플리케이션 서버는 필요하지 않기 때문이다.

웹 애플리케이션이 중심이었다면 Java도 고려할 수 있었지만, 현재 목적에는 Python이 더 적합하다고 판단했다.

## 2026-09-21 — 첨부 포함 파이프라인의 설계 원칙

상태: 이번 문서 작업에서 채택한 **설계 방향**. production 구현 완료나 아래 미결정 도구의 채택을 뜻하지 않는다. 기존 날짜별 기록을 유지하며 별도 ADR 시스템은 만들지 않는다.

### Decision

학교 사이트를 source of truth로 삼고 발견 당시 raw/첨부 원본을 보존한다. raw → extracted → normalized → analyzed를 분리하고 출처별 identity/history를 유지한다. 첨부를 독립 데이터로 관리하며 불완전 추출은 신청 가능성 판단에 반영한다. 목록 소실은 삭제 확정과 구분한다. deterministic 판별과 LLM 의미 해석을 분리하고 알림 멱등성을 영속 상태로 관리한다.

### Rationale

검색 인덱스 지연, 모집 목록 소실, 첨부 전용 자격조건, 수정 공지와 parser/prompt 변경에 대응하기 위해 필요하다. J-Point 혜택만으로 실제 신청 불가 활동을 추천하지 않도록 근거와 profile 조건을 함께 평가한다.

### Alternatives

- URL/요약만 저장: 구현이 작지만 원문 소실 후 검증/재처리 불가능.
- 모든 처리를 한 LLM 호출에 위임: 초기 연결은 쉽지만 실패 격리·날짜 계산·근거 추적·비용 통제가 어려움.
- 항상 OCR/vision: 구현 경로 수는 줄지만 비용과 처리 시간이 증가하고 native 텍스트 활용을 포기함.
- 제목으로 중복 제거: 간단하지만 서로 다른 모집/회차 또는 출처별 조건을 유실할 수 있음.

### Consequences

원본 저장 공간, version/provenance, 단계별 상태 관리가 추가된다. 필요한 단계부터 점진적으로 구현한다. 단일 출처 신규 탐지 우선이라는 기존 범위는 유지한다. 상세 계약은 [design](design.md)의 문서 링크를 따른다.

## 2026-09-21 — 권고안과 아직 결정할 항목

아래는 **권고이며 최종 확정 전**이다. 이번 작업에서는 패키지 설치나 실사이트/실문서 benchmark를 수행하지 않았다.

| 선택 | 권고 / 대안과 trade-off | 결정할 근거/시점 |
| --- | --- | --- |
| 저장소 | SQLite + local blobs / PostgreSQL은 동시성·운영비 증가, DB BLOB은 백업 일관성 대신 DB 크기 증가 | M0에서 운영이 단일 호스트인지 확인하고 확정 |
| adapter 범위 | 공통 Collector + 사이트 Parser, 단순 등록 dict / 전용 Collector는 특수 요청에 유리하지만 중복 가능 | 첫 상세 수집, 두 번째 source로 계약 검증 |
| PDF/HWPX/Office parser | native 우선 / 범용 변환은 운영 의존성과 layout 손실 가능 | 실제 한글·표 fixture의 품질, 라이선스, 설치 가능성 비교 |
| legacy HWP | native → 검증된 converter → PDF/render fallback / 상용 도구는 호환성 대안이나 비용/환경 제약 | 실제 HWP 버전·OS별 변환 성공률 확인, unsupported 처리도 허용 |
| OCR/vision | 부족한 페이지만 / 전체 vision은 비용 큼 | quality threshold와 페이지별 비용 측정 |
| LLM 제공자/model | structured schema 지원과 한국어 자격 판독을 평가 / 로컬 모델은 운영 부담과 품질 검증 필요 | M3 eval 후 확정, 현재 특정 API 미선택 |
| 알림 ambiguous delivery | unknown으로 보류 / 자동 재시도는 누락을 줄이지만 중복 가능 | Discord 전송 구현 시 사용자 선호와 API 동작 확인 |
| profile/priority | 필수성·신청 가능성 gate 후 실익 / 단일 가중합은 불가 활동 고평가 위험 | 실제 profile의 미확인 조건, threshold·임박 window 피드백 |
| 수집 범위/주기 | 단일 board baseline부터 / 전체 backfill은 비용·기존 알림 혼동 증가 | 실사이트 페이지네이션·모집 소실 특성 조사 |
| 보존/예산 | raw 기본 장기 보존, 유료 처리 상한 / 짧은 retention은 재처리 손실 | 파일 크기·일일 신규량 측정 후 수치 확정 |

지금 구현을 시작한다면 첫 지점은 [M0](architecture/repository-review.md)의 HTTP 오류 처리·오프라인 목록 fixture·SQLite 신규 탐지다. 선택지가 모두 확정될 때까지 첫 milestone을 막을 필요는 없다.
