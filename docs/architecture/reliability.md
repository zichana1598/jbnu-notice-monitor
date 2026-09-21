# Reliability, 재처리, 테스트

상태: 제안. 원본/버전 구조는 [파이프라인](notice-pipeline.md), 출력 계약은 [분석 설계](llm-analysis.md)에 정의한다.

## 단계별 실패와 복구

| 상황 | 기록과 처리 |
| --- | --- |
| 일부 source/페이지 실패 | run을 partial/failed로 기록, 다른 source 진행. 불완전 coverage로 missing/삭제 판정 또는 baseline 완료 금지 |
| 개별 행/상세 parse 실패 | raw와 row 오류 보존, 정상 행은 저장 가능. 오류 행을 정상 seen으로 처리하지 않음 |
| 첨부 download 실패 | ref와 상태 보존, 해당 파일만 재시도, snapshot incomplete |
| HWP/변환 실패 | method별 오류와 원본 보존, 지원 가능한 fallback만 수행. renderer가 없으면 vision 불가, 수동 검토 |
| LLM API/schema 실패 | 추출 완료 상태 보존, 분석 작업만 재시도. 기본 중요도를 만들어 성공처럼 저장하지 않음 |
| 수정/삭제/비공개/목록 소실 | 관측과 source event 추가, history 불변. 상태 판정은 파이프라인 문서 규칙 적용 |
| 과거 공지 발견 | baseline/backfill/late_discovery 구분. 게시일 불명은 신규 발행으로 단정하지 않음 |
| AI 오판 | 근거 검증·규칙 override·검토 상태, fixture 추가, 새 prompt로 재분석. 기존 판단 이력 유지 |
| 서버 재시작 | DB의 pending/retry 및 만료 lease 작업 재개; 정상 완료 단계 cache 재사용 |
| 비용 상한 도달 | 원본 수집과 저장 우선, 유료 단계 deferred_budget. 누락을 정상 완료 처리하지 않음 |

## 작업 상태와 retry

처음에는 SQLite와 단일 worker면 충분하다. job 상태는 pending/running/succeeded/retry_wait/blocked/dead로 두고 input key와 processor version에 unique를 건다. 외부 호출 전 짧은 트랜잭션으로 작업을 claim하고 완료 후 결과+후속 작업을 함께 commit한다. 외부 호출 동안 트랜잭션은 열지 않는다. crash 후 만료 lease는 회수한다.

권고 초기값(운영 확정 아님): 일시 네트워크/5xx는 최대 3회, 지수 backoff+jitter, 429는 Retry-After와 일일 예산을 함께 적용한다. 401/403·미지원 포맷·암호화·구조 변경은 무한 재시도 대신 blocked로 둔다. 변경된 인증/adapter/parser 또는 수동 요청 후 재개한다. API schema 오류는 같은 잘못된 응답을 반복 소비하지 않고 제한된 교정 재요청만 허용한다.

dead-letter는 별도 큐 서버 대신 `jobs.status=dead`와 stage/error/attempt/input reference 조회로 충분하다. stage 또는 notice/file/parser-version 단위 재처리를 수동 CLI로 제공한다. 사용자의 재처리 요청은 시도 이력은 보존하고 새 attempt를 만든다. 실패 cache의 해제 조건과 processor version을 구분한다.

## 파일/DB 일관성과 백업

파일 write/fsync/atomic rename이 끝난 blob만 DB에서 참조한다. 파일 성공 뒤 DB commit 전에 죽으면 orphan blob이 생길 수 있으므로 참조 검사 후 유예기간이 지난 orphan만 정리한다. DB만 성공하고 파일이 없는 상태는 무결성 오류로 감지하고 archive 완료로 취급하지 않는다. 작은 migration 버전 테이블을 두고 FK/unique를 활성화한다.

초기 백업은 수동 worker를 멈춘 상태에서 DB와 blob directory를 함께 보관하면 충분하다. 실행 중 복사하려면 SQLite backup 방식과 참조 blob manifest를 사용한다. WAL 사용 중 DB 파일 하나만 복사하지 않는다. 복원 테스트에서 모든 DB blob 참조의 존재와 hash를 확인한다. raw 원본을 삭제하는 retention 정책은 별도 결정 전 적용하지 않는다.

## Notification idempotency의 범위

동일 이벤트를 매번 전송하지 않도록 `delivery_key = recipient + destination + subject(notice 또는 신뢰된 cluster) + event_kind + material_revision`을 unique로 둔다. 마감 reminder는 deadline revision과 reminder window를 추가한다. 모델/prompt 버전은 delivery key에 포함하지 않아 재분석만으로 재알림되지 않게 한다. source 수정과 분석 복구로 신청 판단이 실질적으로 바뀌면 별도 `assessment_changed` 이벤트를 만들되 이전 발송 결과와 비교한다.

분석/규칙 결과 저장과 outbox 생성은 하나의 DB 트랜잭션이다. 전송기는 outbox를 claim하고 성공 시 remote message ID와 sent_at을 기록한다. schema 실패/미완료 알림을 보내는 경우 일반 추천과 구분해서 '첨부 확인 필요' 및 사유를 포함한다. 중요한 학사 hard alert는 LLM 실패 때문에 무조건 유실되지 않게 최소 원문 링크 경로를 둔다.

**DB unique만으로 외부 Discord 전송의 exactly-once를 보장하지 않는다.** 요청이 서버에 전달된 직후 응답이 유실되거나 로컬 성공 기록 전에 종료되면 이미 전송했는지 모호하다. 전송 성공 응답 ID를 받을 수 있는 API 방식을 구현 시 확인한다. ID가 확보되면 수정/재사용하고, 모호한 timeout은 `delivery_unknown`으로 두는 보수적 정책을 권고한다. 자동 재시도하면 중복 가능, 멈추면 누락 가능하다는 trade-off를 사용자 정책으로 확정해야 한다. 초기에는 unknown을 자동 재발송하지 않고 수동 확인하도록 제안한다.

## 비용 통제와 관측

출처별 요청 속도/최대 페이지, 파일 크기/페이지 수, parser 실행 시간, 문서당 vision 페이지/LLM token, 일일 유료 요청/예산을 설정한다. 동시 실행이 생기면 예산 예약을 원자적으로 처리한다. 실패/교정 요청도 비용 집계에 포함한다. 첨부 hash cache와 분석 fingerprint cache로 동일 입력을 반복 과금하지 않는다. 자격조건이 있는 후반부를 자르고 완전 분석이라고 표시하지 않는다.

기록할 지표: source 마지막 성공 시각·coverage·연속 실패, 신규/수정/소실 수, 첨부 실패율, extraction partial 비율, schema 실패율, dead/unknown outbox 수, 단계별 비용과 소요 시간. 초기에는 구조화 로그와 CLI 요약이면 충분하다. 사용자 알림과 운영 오류를 별도 종류로 표시하고 실패 경보 자체의 반복도 제한한다.

## 테스트 전략

실네트워크 없는 고정 HTML/JSON/문서 fixture, 임시 SQLite/파일 저장소, fake clock/HTTP/LLM/Notifier를 기본으로 한다. live smoke는 별도 opt-in이며 학교 사이트의 변경을 탐지하는 보조 수단이다. 기존 테스트는 없으므로 M0부터 추가한다. parser 품질 테스트와 HTTP 재시도 테스트를 분리한다.

| 회귀 사례 | 핵심 assertion |
| --- | --- |
| 신규/재실행/재시작 | 새 source ID만 신규, 동일 입력 두 번 및 재시작 후 추가 이벤트 0 |
| 첫 baseline/과거 공지 | 기존 글 알림 억제, 실패 baseline 미승인, 늦게 발견한 과거 글을 신규 발행과 구분 |
| 본문/마감 수정 | 동일 ID 새 version과 material event, 이전 raw 보존 |
| 첨부 수정 | 같은 URL의 bytes 교체/추가/제거 감지, 다운로드 완료만으로 source 수정 생성 안 함 |
| 목록에서 소실 | 완전한 동일 범위 관측만 missing, 글과 archive 유지, 상세 확인 전 삭제 확정 안 함 |
| 부분 목록/페이지네이션 | failed/partial run으로 missing/closed 전환 없음, 고정 공지 재등장 중복 없음 |
| 동일 공지 중복 | source 내 identity 중복 0, 출처 간 strong cluster 알림 억제, 유사 제목만으로 병합 안 함 |
| 첨부 없음/다운로드 실패 | none과 incomplete 구분, 실패가 다른 첨부를 막지 않음 |
| PDF | native 한글/표 근거 위치, image-only page만 fallback, mixed PDF에서 누락 감지 |
| HWPX | 문단·표의 eligibility와 순서/근거 보존, ZIP 일반 파일과 구별 |
| legacy HWP | 검증한 버전 fixture native 기대값, 실패 시 converter 호출 순서 |
| HWP 변환 실패 | 지원 renderer 있으면 대체 → PDF/vision; 없으면 명시 failure, 허위 성공 없음 |
| DOCX/XLSX/PPTX/image | 문단/셀/slide 위치, sheet 수식 불명, 이미지 추출·자원 제한 |
| MIME 위장/손상/압축 상한 | HTML 오류를 PDF로 처리하지 않음, 파서 격리와 명시 오류 |
| 첨부에만 eligibility | body-only 판단과 달리 첨부 조건이 check에 포함됨 |
| J-Point 있지만 신청 불가 | 명확한 prerequisite unmet이면 최종 not_recommended, 이유/evidence 포함 |
| 임박/마감/날짜 불명 | Asia/Seoul 경계, date-only/연도 생략/선착순 처리, 고정 clock에서 재현 |
| LLM 실패/오답/프롬프트 주입 | retry 제한, 잘못된 schema/evidence 거부, hard alert 보존, 문서 지시 실행 안 함 |
| notification 중복 | outbox UNIQUE, 같은 이벤트 재분석, 두 worker claim, crash 전후; ambiguous send는 unknown |
| parser/prompt/profile 변경 | 새 derived revision, 원본 fetch 없이 재분석, 학교 수정/신규 알림으로 오인 없음 |
| 비용 상한/복원 | 유료 처리 deferred, 원본 보존; DB+blob 복원 후 hash 참조 정상 |

## SW산학멘토링 대표 fixture

이 사례는 **사용자 제공 사례**이며 현재 repository에 실제 공지/첨부 원본이 없고 이번 작업에서 학교 문서로 독립 검증하지 않았다. 실제 문구를 확인한 인용처럼 만들지 않는다.

초기 fixture는 synthetic임을 명시한다: 제목/본문에는 SW산학멘토링과 J-Point 혜택을, 첨부에는 지도교수 + 대학원생 멘토 + 기존 산학협력프로젝트/캡스톤 참여 학부생 등의 팀 조건을 넣는다. fixture manifest에 출처 성격, 기대 fact, attachment locator와 profile 조건을 저장한다. 추후 실제 원본 확보 시 원문 URL/수집일/hash/배포 허용 여부를 기록하고 민감정보를 제거한 버전 또는 로컬 fixture를 사용한다.

세 profile로 검증한다:

- 2학년이며 개인 신규 신청, 기존 프로젝트/팀/교수·멘토 구성이 없다고 **명시한** profile: mandatory 조건 unmet → 높은 J-Point 가치에도 not_recommended.
- 2학년이지만 기존 팀/프로젝트 참여 여부 미제공: uncertain/needs_review. 학년만으로 불가 확정 금지.
- 요건을 충족한 참여자 profile: 가능한 후보로 재평가. 사례명에 대한 고정 제외 rule 금지.

첨부 실패 variant에서는 J-Point만 보고 eligible/high로 확정하지 않아야 한다. native/변환/vision의 실제 품질은 진짜 형식 fixture로 별도 검증하고, mocked fallback 테스트를 HWP 지원 입증으로 간주하지 않는다. LLM은 문자열 완전 일치보다 required fact recall, 근거 연결, 불가 오추천 여부를 평가하며 live eval은 비용 한도 내 별도 실행한다.
