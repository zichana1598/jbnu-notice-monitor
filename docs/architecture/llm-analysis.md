# Normalization과 사용자 relevance

상태: 제안. 현재 분류/LLM/profile 구현은 없다. 원본 모델은 [파이프라인](notice-pipeline.md), 검증 사례는 [회귀 테스트](reliability.md)를 참조한다.

## Normalized와 의미 추출을 구분

normalized snapshot은 metadata, body blocks, attachment texts/blocks, attachment completeness, source 상태, date candidates, evidence index, conflicts를 담는다. raw HTML이나 파일 전체를 그대로 LLM에 전달하지 않는다. 다만 텍스트 축약으로 자격조건이 소실되지 않도록 모든 추출 block을 보존한다.

정규화 코드는 HTML/공백 정리, 날짜 후보 검출, 표/문단 구조와 위치 보존까지 담당한다. `eligibility`, `benefits`, `required_actions`, `contacts`는 evidence에 연결된 의미적 fact로 **LLM structured extraction**에서 작성하는 것을 권고한다. 명확한 사이트 구조화 필드는 deterministic fact로 먼저 채울 수 있다. 정규식만으로 팀 구성 조건을 일반화하면 오판 위험이 크고, 전부 LLM에 맡기면 날짜 계산/재현성/비용이 나빠진다. 따라서 후보 검출 → 의미 판독 → 코드 검증의 혼합 방식을 택한다.

초기에는 LLM 호출 한 번으로 사실 추출과 relevance를 만들되 출력 객체를 구분한다. 여러 profile이 필요해지면 source facts 추출을 공통 cache로 분리하고 사용자 relevance만 재계산한다. 긴 문서는 evidence 범위별 chunk extraction 후 aggregate하되 각 chunk 누락/오류를 최종 completeness에 전파한다. 요약만 재요약하지 않고 자격·마감·혜택 근거 blocks를 최종 단계까지 연결한다.

## 책임 경계

| 판단 | 코드 | LLM |
| --- | --- | --- |
| 신규/버전/파일 동일성 | ID·hash·관측 기준으로 확정 | 담당하지 않음 |
| 중복 게시 | 명시 identity/근거로 cluster, 불확실하면 별도 유지 | 후보 보조만 가능 |
| 날짜/마감 | timezone, 날짜 precision, 현재 시각 비교, 임박 window | 여러 날짜의 의미(신청/행사/제출), 모호한 표현과 충돌 설명 |
| 지원 자격 | 명확한 구조화 조건과 profile 비교, 알려진 mismatch gate | 첨부의 선행조건, 팀 구성, 예외/모호함 해석 |
| 일정 충돌 | 사용자가 제공한 시간표와 검증된 일정 구간 교집합 | 참석 필수/선택 여부 해석; 시간표 미제공은 unknown |
| hard alert | 학사 필수·목표 필수 등 사용자 규칙 | 관련 근거 추출; 경고를 숨길 권한 없음 |
| 실익 | 정책 가중치/정렬/알림 여부 | 프로그램 성격, 경험/포트폴리오 가치, 근거 있는 적합성 |
| 최종 priority | eligibility/completeness·hard alert·기한을 적용해 결정 | 추천 후보와 짧은 근거 제공 |

규칙 전처리에서 제목 키워드 불일치만으로 버리지 않는다. 마감도 행사일을 신청 마감으로 오인하면 안 된다. `date_only`는 날짜 구간으로 보관하고 같은 날은 정확한 종료시각 unknown, 다음 날부터 종료 판단 등 명시 정책을 둔다. '선착순', '상시', '예산 소진 시'는 고정 timestamp로 만들지 않는다. 연도 생략·본문과 첨부 충돌은 추정과 근거를 표시하며 규칙 확정에 사용하지 않는다.

## 사용자 profile과 우선순위

profile은 version/effective date, 소속·학년·학적, 알려진 성적/자격, 팀/연구실/캡스톤 참여 상태, 시간표, 목표/필수요건, 관심사와 알림 선호를 저장한다. 사용자가 주지 않은 성적·팀 소속·시간표는 unknown이다. 2학년이라는 이유만으로 특정 프로그램 참여를 자동 부정하지 않는다.

우선 고려: 공모전/해커톤/경진대회, 프로젝트/개발/AI·SW 경험, J-Point 프로그램·장학생, 현금성 장학금/활동비/상금, 학사 필수, 목표의 필수요건, YELLOW BELT 모집. 전공포인트는 상대적으로 낮게 두고 J-Point와 별도 필드/단위로 관리한다. YELLOW BELT 필수 여부는 검증된 제도 근거가 있어야 하며 명칭만으로 필수라고 단정하지 않는다.

권고 policy 순서:

1. 학사/사용자 목표 필수 hard alert는 일반 활동 추천과 별도 route로 보존한다.
2. 명확한 신청 불가면 benefit 점수가 높아도 `not_recommended`; uncertain/첨부 누락이면 `needs_review`이며 높은 확신의 신청 추천을 금지한다.
3. 신청 가능한 후보 안에서 필수성, 마감 임박, 목표 기여, 개발·수상·금전·J-Point 등을 정렬한다. 미확정 지원은 확정 장학금처럼 합산하지 않는다.
4. 이미 마감된 신규 발견은 기본 모집 추천 억제. 마감 연장/재모집·필수 후속조치는 별도 event다.

구체 가중치/임박 일수/알림 threshold는 사용자 피드백과 fixture 평가 후 결정한다. LLM confidence 숫자는 보정된 확률이 아니며 completeness와 evidence 검증을 대체하지 못한다.

## Structured output 초안

아래는 JSON Schema로 구현할 **계약 초안**이며 현재 실행 가능한 validator가 아니다. 모든 객체는 선언한 필드만 허용(`additionalProperties: false`), 필수 키는 항상 존재, 모르는 값은 null 또는 명시 enum, 누락과 false를 구분한다. boolean|string 혼합 `eligible` 대신 enum을 권고한다.

| 필드 | 타입/제약 |
| --- | --- |
| `schema_version` | 고정 문자열 `1` |
| `evidence` | Evidence[]: `id`, `block_id`, `quote`; block_id는 입력 index에 존재, quote는 그 block의 짧은 원문 구간 |
| `facts.deadlines` | DateFact[]: `kind`(application/event/submission/other), `raw_text`, `local_date` nullable ISO date, `local_time` nullable, `timezone` nullable, `precision`(datetime/date/range/unknown), `evidence_ids` |
| `facts.requirements` | Requirement[]: `id`, `kind`(year/major/grade/team/prerequisite/attendance/documents/other), `description`, `mandatory`(yes/no/unknown), `evidence_ids` |
| `facts.benefits` | Benefit[]: `kind`(experience/award/scholarship/allowance/prize/j_point/major_point/other), `description`, `conditional`(yes/no/unknown), `evidence_ids` |
| `facts.j_point` | `status`(offered/not_offered/unknown), `amount` nullable number ≥0, `conditions` string[], `evidence_ids` |
| `facts.yellow_belt` | `relation`(required/required_elective/related/none/unknown), `category` nullable string, `evidence_ids` |
| `facts.money` | MoneyFact[]: `kind`, `currency` nullable string, `amount_min/max` nullable number ≥0, `basis`(person/team/total/unknown), `conditions`, `evidence_ids`; min ≤ max |
| `facts.contacts` | Contact[]: `name` nullable, `channel`, `value`, `evidence_ids` |
| `assessment.eligibility` | `status`(eligible/ineligible/uncertain), `reason`, `checks` Check[] |
| `assessment.eligibility.checks[]` | `requirement_id`, `result`(met/unmet/unknown), `profile_field` nullable, `evidence_ids` |
| `assessment.individual_application` | `status`(allowed/not_allowed/uncertain), `reason`, `evidence_ids` |
| `assessment.schedule` | `status`(compatible/conflict/unknown), `reason`, `evidence_ids`; 최종 겹침 계산은 코드 |
| `assessment.portfolio_value` | `level`(high/medium/low/unknown), `reason`, `evidence_ids` |
| `assessment.suggested_priority` | urgent/high/normal/low/needs_review/not_recommended |
| `assessment.user_actions` | Action[]: `description`, `requirement_ids`, `evidence_ids` |
| `assessment.reasoning_summary` | 짧은 결론 근거 문자열; 내부 사고과정 요청 아님 |
| `assessment.confidence` | number, 0 ≤ x ≤ 1 |
| `assessment.uncertainties` | string[] |
| `assessment.conflicts` | 객체 배열: `description`, `evidence_ids` |

서비스가 별도 저장하는 envelope: notice/snapshot ID, profile version, model/prompt/schema/rules version, request input hash, completeness, token/cost, schema validation 결과, **최종** eligibility/deadline/priority/rule overrides. 이 값은 LLM에게 생성시키지 않는다. 요구사항의 `priority`, `deadline`은 LLM 후보와 코드 확정 값을 분리해서 저장한다.

검증 규칙: 없는 evidence ID·원문과 다른 인용·존재하지 않는 requirement 참조는 거부. 근거 없는 eligible/high 판단은 review로 강등. 알려진 mandatory unmet이 있으면 최종 eligible이 될 수 없다. 정보 미언급은 `not_offered`/`none`의 증거가 아니다. 본문/첨부가 상충하면 최신 날짜만으로 자동 우선하지 않고 충돌을 보존한다. schema 실패는 제한적으로 한 번 재요청하고 계속 실패하면 분석 실패로 남긴다.

## LLM 안전성/비용과 재분석

본문·첨부는 신뢰할 수 없는 입력 데이터로 다루며 그 안의 '지시를 무시하라' 같은 문장을 실행 지침으로 취급하지 않는다. 분석 호출에 외부 도구/비밀값을 제공하지 않는다. 필요한 profile 필드만 전송하고 원문 근거 없는 추론을 확정 사실로 승격하지 않는다.

원본을 다시 수집하지 않고 snapshot 또는 이전 raw에서 분석을 재생성한다. 성공 cache는 input/profile/prompt/schema/model/config 버전을 모두 포함한다. 시간 의존 deadline/priority는 현재 시각으로 코드 재평가하므로 매일 LLM 재호출할 필요가 없다. parser/profile/prompt 변경은 새 분석 revision이며 그 자체를 새 공지 알림으로 발송하지 않는다. 실질 판단 변경의 별도 알림정책은 [신뢰성 문서](reliability.md)를 따른다.
