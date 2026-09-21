# 공지 파이프라인과 저장 모델

상태: 향후 구현을 위한 권고 초안. 현재 구현과 순서는 [조사 문서](repository-review.md), 선택의 상태는 [결정 기록](../decisions.md)을 따른다.

## Source와 책임

Source discovery는 초기에 수동으로 학교 링크를 확인해 등록하는 작업이다. 등록 정보는 안정적인 `source_key`, 사이트/게시판 ID, 시작 URL, adapter 이름/버전, 목록 범위·페이지네이션 전략, 상세 재조회 주기, 허용 다운로드 호스트, source timezone으로 구성한다. `csai` 하나로 모든 학부 게시판을 식별하지 않는다. 예를 들어 `csai.academic`, `csai.general`, `sw.programs`는 제안 이름이며 실제 URL/카테고리 매핑은 아직 검증하지 않았다.

| 컴포넌트 | 책임/계약 |
| --- | --- |
| 공통 HTTP Collector | timeout/상태 코드/redirect 처리, bytes·URL·헤더·응답 시각 반환. HTML 의미 해석 안 함 |
| 사이트별 Parser/Adapter | `parse_list(raw) -> entries, next_requests, coverage, errors`, `parse_detail(raw) -> detail, attachment_refs, source_state, errors`. 요청 구성과 사이트 의미 해석 담당; 네트워크 실행/DB/개인화는 core에 위임 |
| Pipeline | 요청 실행, raw 선보존, 단계 진행 및 재시도 조정. 초기 단순 함수와 등록 dict |
| Detector/Storage | source identity, 관측 상태, version, 신규/수정 이벤트를 트랜잭션으로 기록 |
| Attachment downloader | 첨부 refs를 내려받고 원본 blob 및 독립 상태 기록 |
| Document parser | 형식별 evidence blocks와 품질/오류 산출 |
| Normalizer | body와 첨부 blocks를 동일한 snapshot에 묶고 출처·위치 유지 |
| Rules/LLM/Ranking | [개인화 분석 계약](llm-analysis.md)에 따라 후보·사실·사용자 적합성·최종 알림정책 분리 |
| Notifier | 영속 outbox를 소비, 전송 결과 기록 |

일반 게시판·학과·사업단·프로그램 신청은 같은 도메인이어도 별도 source다. 프로그램 신청 adapter는 모집 상태와 프로그램 고유 ID를 해석한다. JS가 필요하면 먼저 사이트 자체의 공개 데이터 응답을 확인하고, 불가능할 때만 브라우저 수집 의존성을 검토한다. 새 source는 등록과 parser/fixture 추가로 처리하고 core 조건문에 사이트명을 늘리지 않는다. 아직 두 번째 사이트가 없으므로 범용 plugin framework는 만들지 않는다.

등록 후보는 다음과 같다. URL과 공개 접근 방법은 추가 조사 대상이며 현재 지원 목록이 아니다.

| 사이트 | 개별 source 후보 | 확인할 특성 |
| --- | --- | --- |
| 전북대학교 전체 | 전체 공지 게시판 | 공지 고정/페이지네이션/상세 ID |
| 컴퓨터인공지능학부 | 학사공지, 일반공지, 사업단공지, 취업정보 | 게시판별 ID namespace와 현재 코드 URL의 카테고리 |
| SW중심대학사업단 | 공지사항, 프로그램 신청, J-Point 관련 페이지 | 신청 목록의 모집 종료 후 소실, 프로그램 ID, 상세/첨부 접근 |
| 향후 다른 사이트 | 명시 등록한 게시판/프로그램 페이지 | 기존 adapter 재사용 가능성, 신규 fixture |

## 데이터 흐름 및 identity

1. 실행 기록을 만들고 목록 응답 bytes를 먼저 보존한다. 원본 파싱 실패도 archive와 오류는 남긴다.
2. 목록 ID는 `(source_id, source_specific_id)`로 unique 처리한다. 제목/날짜로 신규를 판별하지 않는다. ID가 없는 출처만 adapter가 검증한 canonical URL을 대안으로 쓰며 identity 방식과 URL alias를 기록한다. 의미 있는 query parameter를 임의로 제거하지 않는다.
3. 첫 성공 수집은 baseline 후보로 저장하고 기본 신규 알림은 억제한다. 실패 실행은 baseline을 완료 처리하지 않는다. 최초 스캔 범위 밖에서 뒤늦게 발견한 글은 `late_discovery`로 구분한다. `discovered_at`은 최초 로컬 관측, 게시일과 다르다.
4. 신규뿐 아니라 관측한 기존 글도 상세 재조회한다. 활성/마감 임박은 자주, 오래된 공지는 느리게 재조회하고 정기 범위 확장을 둔다. 조건부 GET의 ETag/Last-Modified는 힌트이며 주기적 무조건 조회로 잘못된 validator와 동일 URL 첨부 교체를 검사한다. 조회 간격 사이에서 생겼다 사라진 공지를 완전히 보장할 수는 없다.
5. 상세 raw와 구조화 metadata를 저장한 후 첨부 ref마다 다운로드 작업을 남긴다. 모든 발견 첨부의 원본 보존을 시도하고 크기 제한/접근 실패는 명시적 미완료로 남긴다.
6. 첨부 결과가 없거나 일부 실패해도 normalized/analysis는 `incomplete`로 생성 가능하다. 이후 첨부가 복구되면 새 normalized revision으로 재분석한다.
7. 규칙 → LLM → 규칙 검증/ranking → outbox 순으로 진행한다. 수집과 알림 성공 상태를 하나의 seen 플래그로 합치지 않는다.

## Hash와 수정

- `raw_hash = SHA-256(수신 bytes)`는 원본 무결성과 저장 중복 제거용이다.
- `semantic_hash`는 adapter 버전과 함께 제목/본문/작성자/게시일/수정일/명시 상태/첨부 ref 등 의미 필드를 정규 직렬화해 계산한다. 조회수/메뉴/세션 토큰은 제외하되 원본에는 남긴다.
- 첨부 완료 전에는 attachment manifest를 `pending`으로 둔다. 완료 후 다운로드 hash를 포함한 resolved manifest revision을 만든다. pending→resolved를 학교의 수정 이벤트로 오인하지 않는다.
- 이전에 성공적으로 관측한 파일 hash와 새 hash가 다르면 `attachment_changed` source event다. 같은 URL/이름도 다시 확인한다. 첨부 추가/제거와 순서만 바뀐 경우를 구분한다.
- parser 변경으로 추출이 달라지면 derived revision만 생성한다. 학교 콘텐츠 수정과 로컬 재처리를 구분한다. hash 계산 규칙 자체도 버전 관리한다.
- 본문/마감/자격/첨부 변경은 알림 후보이고 단순 공백 변경은 억제한다. 이벤트에는 이전/새 revision을 연결한다.

## 상태는 한 enum으로 합치지 않는다

`listing_presence = present | missing | unknown`, `access_state = accessible | unavailable | deleted_confirmed | unknown`, `application_state = active | closed | unknown`을 분리한다. `last_seen_at`, `last_checked_at`, `missing_since`, 관측 근거도 보관한다.

목록 일부 조회/페이지 이동/통신 실패만으로 삭제·마감을 선언하지 않는다. 성공적으로 같은 범위를 확인한 경우만 missing 판단에 사용한다. active 목록에서 사라졌다면 missing을 기록하고 상세 URL을 재확인한다. 403은 접근 불가, 단발 404도 일단 unavailable, 명시 삭제 안내 또는 adapter가 검증한 반복 근거가 있어야 deleted_confirmed로 전환한다. 마감은 공지의 명시 상태 또는 검증한 신청 마감 시각에 따른 별도 파생 상태다. 어떤 경우에도 원본/history는 제거하지 않는다.

## 중복은 두 수준

동일 source ID 재등장은 같은 공지다. 서로 다른 게시판의 글은 각 identity/archive/version을 유지하면서 `notice_cluster`로 연결한다. 같은 attachment hash는 파일 중복일 뿐 같은 행사라는 증거가 아니다. 명시적인 동일 프로그램 ID/원문 링크가 있으면 강한 연결 근거, 제목 유사성·날짜·주최·내용 일치는 후보 근거다. 애매한 경우 병합하지 않는다. 자동 중복 억제는 신뢰할 수 있는 cluster에만 적용한다. 출처별 추가 자격/마감 차이는 보존하고 충돌로 분석한다. 잘못된 cluster를 해제할 수 있게 근거와 연결 시점을 남긴다.

## 저장 방식 선택

권고: 로컬 SQLite + content-addressed 파일 저장. 개인/단일 프로세스에서는 관리 부담이 작고 트랜잭션과 unique 제약을 사용할 수 있다. PostgreSQL은 여러 호스트/동시 writer·운영 서버가 필요해질 때 검토한다. SQLite WAL도 동시 writer는 하나라는 제약이 있으므로 외부 다운로드/LLM 호출 중 DB 트랜잭션을 잡지 않는다. [SQLite 공식 WAL 문서](https://www.sqlite.org/wal.html)

대안: 모든 bytes를 DB BLOB에 넣으면 일관된 백업이 쉬워지지만 대형 첨부가 DB/백업을 키운다. 파일 + DB는 별도 무결성 관리가 필요하지만 원본 관리와 이관이 단순하다. 초기 object storage는 불필요하다. DB에 절대 로컬 경로 대신 storage key를 넣어 나중에 파일 backend를 옮길 수 있게 한다.

## DB 초안

모든 ID/FK/unique는 실제 migration에서 강제한다. 시각은 UTC 저장, 표시·마감 해석은 Asia/Seoul. 날짜만 알면 date와 precision을 유지하며 거짓 정밀도를 만들지 않는다. JSON 열은 가변 payload용이고 identity·상태·재시도·검색 핵심은 일반 열로 둔다.

| 테이블 | 핵심 필드 / 제약 |
| --- | --- |
| `sources` | id, source_key UNIQUE, config_json, adapter_version, baseline_state, timezone |
| `crawl_runs` | id, source_id FK, started/finished_at, status, requested_scope, coverage_json, errors |
| `blobs` | sha256 PK, storage_key UNIQUE, byte_size, detected_format, created_at |
| `raw_captures` | id, run_id FK nullable(재조회), request/final_url, fetched_at, http_status, selected_headers, blob_hash FK; 목록/상세/오류 응답 구분 |
| `notices` | id, source_id FK, source_specific_id, canonical_url, discovered_at, last_seen_at, current_version_id, 세 종류 상태, missing_since; UNIQUE(source_id, source_specific_id) |
| `notice_observations` | id, notice_id, run_id, observed_at, listing/detail 결과, raw_capture_id, status_reason; 실패/소실 이력 |
| `notice_versions` | id, notice_id FK, sequence, raw_capture_id, semantic_hash, hash_policy_version, title, body_text, author, published_at, source_updated_at, date_precision, observed_at; UNIQUE(notice_id, sequence) |
| `attachment_refs` | id, notice_version_id FK, source_attachment_id 또는 adapter ref_key, original_url, filename, ordinal; UNIQUE(notice_version_id, ref_key) |
| `attachment_fetches` | id, attachment_ref_id FK, fetched_at, status, http_status, blob_hash nullable FK, error; 파일 재확인 이력 유지 |
| `extractions` | id, blob_hash FK, parser_name/version, config_hash, status, method_chain_json, output_blob_hash, quality_json, error; UNIQUE(blob_hash, parser_name, parser_version, config_hash) |
| `normalized_snapshots` | id, notice_version_id FK, manifest_hash, input_extraction_ids, normalizer_version, payload_blob_hash, completeness; UNIQUE(input_fingerprint, normalizer_version) |
| `user_profiles` | id (version row PK), profile_key, version, effective_at, payload_json; UNIQUE(profile_key, version) |
| `analyses` | id, snapshot_id FK, profile_version_id FK, model, prompt/schema/rules_version, input_hash, status, result_json, usage/cost, created_at; 성공 cache key UNIQUE |
| `notice_clusters`, `cluster_members` | cluster id, notice_id FK, evidence, confidence, created_at, revoked_at; 활성 소속 중복 제약 |
| `notice_events` | id, notice_id FK, kind, before/after revision, evidence, observed_at, event_key UNIQUE |
| `jobs` | id, stage, input_key, processor_version, status, attempts, next_attempt_at, lease_until, error; UNIQUE(stage, input_key, processor_version) |
| `notification_outbox` | id, delivery_key UNIQUE, event_id, analysis_id, destination_key, payload_json, status, attempts, next_attempt_at, remote_message_id, sent_at |

M0에는 sources/crawl_runs/blobs/raw_captures/notices 및 최소 관측 상태만 필요하다. 이후 해당 기능 도입 시 분리한다.

## 파일 보존 및 재처리 입력

`data/monitor.sqlite3`, `data/blobs/sha256/<prefix>/<hash>`에 원본 bytes와 추출/normalized 대형 결과를 저장한다. 확장자는 판별 metadata이며 identity가 아니다. 원본 HTML뿐 아니라 JSON 응답·첨부·변환 PDF·사용한 페이지 이미지·추출 blocks·LLM 입력/출력·버전·오류를 서로 연결한다. source URL만 남겨서는 소실 후 재처리가 불가능하다.

raw와 attachment original은 기본 장기 보존, derived 결과도 초기에는 보존한다. 비용이 커지면 재생성 가능한 렌더링부터 제거 정책을 별도 결정한다. prompt 템플릿/버전, 실제 입력과 truncation 범위, provider/model 식별, profile snapshot을 남겨 판단 경위를 재현한다. 동일 모델의 비결정적 출력을 동일하게 재생성한다는 보장은 아니다. 인증값/webhook은 DB payload·로그·fixture에 넣지 않는다.
