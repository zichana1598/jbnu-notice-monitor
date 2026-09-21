# Repository 조사 및 구현 계획

조사일: 2026-09-21. 이 문서는 로컬 파일을 직접 읽은 결과다. 사이트 실수집이나 실제 첨부파일 검증은 이번 작업에 포함하지 않았다. 설계 진입점은 [design](../design.md)이다.

## 확인된 현재 상태

| 경로 | 확인한 내용과 한계 |
| --- | --- |
| `README.md` | 서비스 목표와 Collector → Parser → Detector → Classifier → Notifier를 설명. Features는 목표이며 구현 완료 목록이 아님 |
| `AGENTS.md` | Python 프로젝트의 단순성, 책임 분리, 단일 게시판 신규 탐지 우선, 구현 후 관련 테스트, 설계 문서 갱신을 요구. `docs/`를 문서 위치로 지정 |
| `docs/design.md` | 기존 상위 설계. 기본 Notice, 단계별 책임, 개발 순서와 미결정 항목 존재 |
| `docs/decisions.md` | 날짜별 결정 기록. Python 사용, Collector/Parser 분리만 확정되어 있었음. 별도 ADR 번호/템플릿 관례 없음 |
| `src/main.py` | `https://csai.jbnu.ac.kr/csai/29107/subview.do`를 fetch 후 parse. 최상위 실행 코드이며 결과 저장/출력 없음 |
| `src/collectors/http_collector.py` | `requests.get(url)` 후 `response.text` 반환. timeout, 상태 코드 검사, 재시도, 응답 bytes/헤더 보존 없음 |
| `src/parsers/csai_parser.py` | BeautifulSoup으로 `tbody tr`, `strong`, `a`, `_artclTdRdate` 파싱. URL의 끝에서 두 번째 조각을 ID로 사용. `source="csai"`. assert 기반 필수 태그 검사로 한 행 이상이 전체 parse를 중단할 수 있음 |
| `src/models.py` | dataclass Notice: id/source/title/url/published_at, 모두 str. 본문/첨부/버전 없음 |
| `src/storage/`, `src/filters/`, `src/notifiers/` | 디렉터리만 있고 구현 파일 없음 |
| `tests/`, `data/` | 비어 있음. 회귀 fixture와 저장 데이터 없음 |
| `requirements.txt` | requests, beautifulsoup4만 선언, 버전 고정 없음 |
| `.gitignore` | AGENTS.md, data/, .obsidian/, .venv/ 제외. 일부 `__pycache__/*.pyc`가 이미 추적됨. 이번 작업에서 정리하지 않음 |
| `.agents/`, `.codex/` | 비어 있음. 추가 instruction 없음 |

`planning/`, `research/`는 현재 checkout에 없다. 따라서 기존 역할을 추정하거나 새로 만들지 않는다. README와 docs의 모든 기존 Markdown, 전체 production Python 4개, requirements와 작업 규칙을 읽었다. `.venv`는 외부 패키지 환경으로 프로젝트 설계 조사 대상에서 제외했다. 작업 시작 시 git status는 깨끗했다.

기존 설계의 첫 출처 설명은 전북대학교 게시판 일반을 가리키지만 실제 코드는 컴퓨터인공지능학부 URL을 사용한다. 첫 milestone은 **현재 코드의 한 게시판**으로 검증하고, 게시판의 정확한 카테고리명·페이지네이션·상세 구조는 실사이트 조사 후 등록한다. 사용자가 열거한 다른 사이트의 adapter가 이미 있다고 보지 않는다.

## 유지와 변경

유지: Python, requests/BeautifulSoup, 공통 HTTP Collector와 사이트별 Parser 분리, 작은 모듈, 수동 실행, 단일 출처 우선. 기존 `parse(html) -> list[Notice]`는 최초 목록 회귀 테스트의 출발점으로 활용한다.

변경 제안: 응답 원본 보존, board 단위 source ID, 명시적인 parse 오류/coverage, SQLite 신규 판별을 먼저 추가한다. 이후 상세·첨부·버전 추적을 쌓는다. 기존 Classifier 책임은 규칙/LLM/최종 ranking으로 세분화하지만 별도 서비스로 배포하지 않는다. 초기 모델은 목록 요약으로 유지한 뒤 상세 모델과 분리하며 대규모 일괄 재작성하지 않는다.

## 구현 순서와 종료 조건

| 단계 | 범위 | 완료를 판단할 증거 |
| --- | --- | --- |
| M0 — 첫 milestone | 현재 단일 게시판, HTTP 오류 처리, 목록 fixture, raw 목록 저장, SQLite identity, baseline와 신규 탐지, 수동 CLI | 같은 입력 재실행 신규 0, 새 ID만 신규, 실패 시 baseline 미승인, 재시작 후 결과 유지 |
| M1 — 수집/archive MVP | 동일 게시판 상세·원본·모든 첨부 다운로드, hash/version, missing 상태, PDF native 추출 | 본문·동일 URL 파일 교체 탐지, 사라진 글 원본 유지, 실패 첨부만 재시도 |
| M2 — 문서 분석 안정화 | HWPX 및 실제 관측 형식, legacy HWP 품질 비교/변환, 제한적 OCR/vision, normalized와 재처리 | 첨부 eligibility 근거 보존, HWP 실패로 글 유실 없음, parser 변경 재처리 |
| M3 — 개인화/알림 | profile, 규칙, schema 검증 LLM, ranking, Discord outbox | SW산학멘토링 회귀, 불확실성 표시, API 실패 복구, 중복 발송 경계 검증 |
| M4 — 확장 | 두 번째 adapter로 계약 검증 후 다른 board/프로그램 신청 페이지, 중복 cluster, 스케줄링/배포 | 출처 하나 실패해도 나머지 진행, 모집 목록 소실 시 history 유지 |

M0 완료 전 AI 분류·다중 사이트·스케줄링·배포를 구현하지 않는 AGENTS.md 원칙을 유지한다. 이번 작업은 모든 단계의 설계만 기록한다.

## 예상 파일 변경 (아직 구현하지 않음)

| 시점 | 수정/추가 경로 | 책임 |
| --- | --- | --- |
| M0 수정 | `src/main.py`, `src/models.py`, `src/collectors/http_collector.py`, `src/parsers/csai_parser.py` | CLI 진입, 목록 계약 보완, 응답 envelope, parse 진단 |
| M0 추가 | `src/storage/sqlite_store.py`, `src/storage/archive.py`, `src/detector.py` | identity/baseline, bytes 보관, 신규 탐지 |
| M0 추가 | `tests/test_csai_parser.py`, `tests/test_detector.py`, `tests/test_collector.py`, `tests/fixtures/csai/` | 오프라인 첫 milestone 검증 |
| M1 추가 | `src/pipeline.py`, `src/sources.py`, `src/collectors/attachment_downloader.py`, `tests/test_archive.py`, `tests/test_versions.py` | 단계 연결, 단일 adapter 등록, 첨부/버전 |
| M2 추가 | `src/parsers/documents/`, `src/normalization.py`, `tests/test_documents.py`, `tests/test_reprocessing.py`, `tests/fixtures/documents/` | 관측된 형식부터 모듈 추가, 추출 및 재처리 |
| M3 추가 | `src/filters/rules.py`, `src/filters/llm_analysis.py`, `src/filters/ranking.py`, `src/filters/analysis_schema.json`, `src/notifiers/discord.py`, `src/storage/jobs.py`, `src/storage/outbox.py`, `tests/test_relevance.py`, `tests/test_outbox.py`, `tests/fixtures/sw_mentoring/` | 분석, 내구성 작업 상태, 알림 |
| M4 추가 | `src/parsers/<site>_parser.py`, 필요 시 `src/adapters/`, `tests/test_adapters.py` | 두 번째 출처에서 실제 공통점이 확인되면 adapter를 패키지로 확장 |
| 필요 단계 수정 | `requirements.txt`, `README.md`, `docs/design.md`, `docs/decisions.md`, `.gitignore` | 검증된 의존성만 추가, 사용법/결정 갱신, 산출물 제외 |

이름은 예상안이며 파일 수 자체가 요구사항은 아니다. 초반에는 storage 함수와 단순 등록 dict면 충분하다.

## 줄일 설계

Kafka/Kubernetes/마이크로서비스, 외부 작업 큐, 범용 크롤링 프레임워크, 자동 source discovery, vector DB, 임베딩 중복 판별, 모든 포맷 동시 지원, 사용자 UI, 복잡한 ORM은 도입하지 않는다. PostgreSQL·object storage·다중 worker는 측정된 필요가 생길 때 전환한다. 상세 테이블도 해당 단계에 도달했을 때 추가한다.
