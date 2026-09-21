# Attachment processing

상태: 제안. 현재 첨부 다운로드/parser 구현과 실제 파일 fixture는 없다. [저장 모델](notice-pipeline.md)과 [실패 정책](reliability.md)을 함께 따른다.

## 다운로드와 실제 형식

발견한 모든 첨부 ref를 기록하고 원본 bytes 다운로드를 시도한다. 특정 확장자나 relevance로 미리 제외하지 않는다. 네트워크 stream으로 임시 파일에 쓰면서 크기 제한과 SHA-256을 계산하고, 완료 검증 후 원자적 rename과 DB 연결을 수행한다. 중간 다운로드는 성공 blob으로 등록하지 않는다. 동일 bytes는 한 blob을 공유하지만 URL·파일명·출처별 연결은 각각 보존한다.

확장자, Content-Type, Content-Disposition은 힌트다. magic bytes와 container 내부 구조로 확인한다. ZIP이라는 사실만으로 HWPX/DOCX/XLSX/PPTX를 구분할 수 없으므로 entry/manifest를 검사한다. OLE container도 HWP로 단정하지 않고 내부 HWP 식별 정보를 확인한다. PDF URL이 HTML 로그인/오류 페이지를 반환하면 download 결과를 `unexpected_content`로 남기고 parser에 PDF로 넘기지 않는다. 주장된 MIME과 판별 결과를 둘 다 저장한다.

크기·redirect 수·timeout·압축 해제 총량·entry 수·CPU/메모리·페이지 수의 상한을 설정한다. ZIP 경로 탈출, 외부 XML entity, 매크로/외부 링크 실행은 허용하지 않는다. 다운로드 URL/redirect는 source에 등록한 공개 호스트를 검증하며 파일명은 로컬 경로로 사용하지 않는다. 상한 초과는 조용한 생략이 아니라 `blocked_limit` 미완료 상태다. 구체적인 상한은 fixture 크기 측정 후 확정한다.

## 형식별 전략

| 실제 형식 | 1차 추출 | 품질 부족/실패 시 | 보존할 위치 정보 |
| --- | --- | --- | --- |
| PDF | native text + layout/table blocks | 부족한 페이지만 render → 로컬 OCR 가능 시 평가 → vision | page, block, bbox, table row/column |
| HWPX | ZIP/XML native parser, 문단/표/section 순서 | 지원하지 않는 요소·내장 이미지별 추출/렌더링 가능성 평가 | section, paragraph, table/cell |
| DOCX | native 문단/표/헤더·각주 등 범위 선언 | embedded image 또는 표현 누락 부분만 vision/변환 | paragraph/table/cell, 관계 ID |
| XLSX | sheet/cell 값, 수식과 cached value 구분, 병합셀 구조 | 이미지·차트에서만 추가 추출 검토 | sheet, cell/range; 숨김 여부 |
| PPTX | slide 텍스트/표, notes 별도 표시 | 텍스트 없는 slide/도표만 render/vision | slide, shape, notes |
| legacy binary HWP | 버전 확인 후 native extraction 품질 평가 | 지원되는 headless converter → PDF native → 부족 페이지 render → vision | native section/표 또는 변환 PDF page; 변환 좌표임을 표시 |
| image | 이미지 검증 후 OCR/vision 추출 | 회전/해상도 보정 또는 수동 검토 | image index/bbox |
| 미지원/암호화/손상 | 원본과 명시 실패 보존 | 다른 지원 도구 또는 수동 검토 | 가능한 metadata만 |

이미지는 native 텍스트가 없으므로 OCR/vision 대상이지만 원본별 한 번만 처리한다. 로컬 OCR과 vision 선택은 한글 표·자격조건 fixture의 품질/비용 비교 후 결정한다. 표를 평문으로 무작정 이어 붙이지 말고 행/열 및 원문 범위를 유지한다. XLSX 수식을 실행하거나 외부 데이터를 갱신하지 않으며 cached value가 없으면 unknown으로 표시한다.

## Legacy HWP의 실제 한계

`pyhwp`는 HWP v5 처리 후보이지 모든 HWP 버전·레이아웃의 안정적 처리가 확인된 선택이 아니다. [프로젝트 공식 문서](https://pyhwp.readthedocs.io/en/latest/)

LibreOffice는 headless/CLI PDF 변환 기능을 제공하지만, 그 사실은 수집한 HWP 파일의 import filter와 정확한 변환을 보장하지 않는다. 실제 OS, converter 버전, 지원 포맷 및 결과 품질을 고정 fixture로 검증해야 한다. [LibreOffice 공식 CLI 문서](https://help.libreoffice.org/latest/gl/text/shared/guide/start_parameters.html?DbPAR=WRITER&System=LIN)

**HWP를 PDF/이미지로 변환하지 못하면 vision으로 바로 넘어갈 수 없다.** native와 converter 모두 실패하고 다른 검증된 renderer도 없다면 `failure/unsupported_conversion`으로 끝내고 원본을 보존한다. 잘못 렌더링된 PDF를 정상 extraction으로 취급하지 않는다. 도구별 별도 임시 디렉터리·프로세스 timeout·실행 자원 제한을 적용하고 원본을 덮어쓰지 않는다. 상용 변환 도구는 라이선스/설치 가능성/비용을 확인한 뒤 대안으로 결정한다.

## 추출 결과 계약

`ExtractionResult`는 blob hash, parser 이름/버전/config hash, `status = success | partial | failure`, method chain, blocks, quality, errors, derived artifact hashes를 갖는다.

각 block에는 안정적인 evidence ID, 텍스트, heading/table 구조, page/section/sheet/cell 등의 locator, method와 경고를 넣는다. method chain은 각 native/convert/render/OCR/vision 시도의 시작·종료·성공 여부와 오류 code를 보존한다. errors에는 retryable 여부, 실패 단계, 안전하게 정리한 message를 둔다. `partial`은 누락 페이지/표/이미지와 실제 처리 범위를 반드시 명시한다.

품질은 글자 수뿐 아니라 페이지별 텍스트 존재, 깨진 문자 비율, 읽기 순서, 표 구조, 이미지 전용 영역, 총 페이지 대비 처리 범위를 확인한다. 텍스트가 많이 나와도 자격 표가 이미지면 complete가 아니다. 임계값은 한글 fixture로 조정하고 근거 없는 success를 피한다. PDF native/OCR API의 존재와 텍스트 순서 문제는 [PyMuPDF 추출 문서](https://pymupdf.readthedocs.io/en/latest/recipes-text.html), [OCR 문서](https://pymupdf.readthedocs.io/en/latest/recipes-ocr.html)를 참고했다. 특정 라이브러리 채택은 아직 미정이다.

## Cache와 부분 실패

cache key는 `blob_hash + parser_name/version + config_hash`이며 converter/OCR 모델/언어/렌더 해상도도 config fingerprint에 포함한다. 같은 파일이 여러 공지에 있어도 extraction은 재사용한다. 성공 cache만 영구 재사용하고 일시 실패를 영구 cache로 고정하지 않는다. unsupported 결과는 같은 도구 구성에서 반복 실행하지 않되 새 parser 버전에서는 재시도한다.

공지에 첨부가 없으면 `attachments_state=none`인 완전한 입력일 수 있다. 첨부가 있는데 다운로드 실패하면 `incomplete`이고 텍스트 없음과 구분한다. 실패 하나가 다른 첨부/공지의 진행을 막지 않는다. 비용 상한 때문에 fallback이 연기되면 `deferred_budget`로 남기고 신청 가능성 판단에서 누락 근거를 표시한다.
