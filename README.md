# JBNU Notice Monitor

전북대학교 공지사항을 자동으로 수집하고,
새로운 공지 중 중요한 정보를 선별하여 Discord로 알려주는 서비스입니다.

## 목표 기능

- 전북대학교 및 학부 공지 수집
- 신규 공지 탐지
- 사용자 관련성 및 중요도 분류
- Discord 알림

## Architecture

목표 흐름: 수집 → 원본 보존 → 첨부 추출 → 정규화 → 규칙/LLM 분석 → 알림

현재 구현은 컴퓨터인공지능학부 한 게시판의 목록 수집·파싱까지입니다.
저장·신규 탐지·첨부 분석·Discord 알림은 아직 구현하지 않았습니다.

자세한 설계는 [docs/design.md](docs/design.md)를 참고하세요.

## Getting Started

> 개발 중

## Documentation

- [Design](docs/design.md) — 목표 구조와 상세 문서 안내
- [Repository 조사와 구현 계획](docs/architecture/repository-review.md)
- [설계 결정 및 미결정 사항](docs/decisions.md)
