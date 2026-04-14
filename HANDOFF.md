# HANDOFF — 책무기술서 파서 세션 이어가기 문서

> 용도: 새 Claude 세션이 이 파일 하나만 읽고 맥락을 5분 안에 복원하는 목적.
> 갱신 원칙: 세션 종료 시 "마지막 세션 요약"만 업데이트. 나머지 섹션은 구조 변경 시에만 수정.

---

## 0. 새 세션 시작 방법

```
1. 이 파일을 Read
2. README.md 요약 확인
3. "마지막 세션 요약" 섹션에서 현재 위치 파악
4. 막히면 하단 "참조 문서" 경로 순으로 Read
```

---

## 1. 프로젝트 한 줄 요약

금융회사 책무기술서(DOCX/HWP/PDF) → 통일 JSON → XLSX → ICR의 Java 파서로 흘려보내는 전처리 파이프라인. 54개사 대응 목표, 현재 시드 2개(IBK DOCX, 라이나 HWP)로 Core 확정 중.

---

## 2. 현재 상태 (Phase)

| Phase | 범위 | 상태 |
|---|---|---|
| **1** | DOCX extractor + classifier + normalizer + xlsx_writer, IBK E2E | 🟡 스캐폴딩 완료, fixture 대기 |
| 2 | HWP extractor(pyhwp) + variant handlers + 3단계 검증, 라이나 E2E | ⏸ 대기 |
| 3 | 신규 회사 add-on (PDF 포함) | ⏸ 샘플 유입 시 |

---

## 3. 완료된 것 (Done)

| 파일 | 역할 |
|---|---|
| `pyproject.toml` | PEP 621, deps: python-docx/pyhwp/openpyxl/pdfplumber/pytest |
| `README.md` | 프로젝트 개요 + 확장 규칙 |
| `.gitignore` | 원본 파일(.docx/.hwp/.pdf/.xlsx) 커밋 차단 |
| `src/chaekmu_parser/__init__.py` | 패키지 초기화 |
| `src/chaekmu_parser/models.py` | Raw 계층(RawDocument/RawTable) + Parsed 계층(ParsedDocument/Executive/...) 데이터 모델 |
| `src/chaekmu_parser/extractors/base.py` | `BaseExtractor` 추상 인터페이스 (`format_name`, `can_handle`, `extract`) |
| `src/chaekmu_parser/classifier.py` | 라벨 기반 테이블 유형 분류 (EXEC_INFO/COMMITTEE/RESP/OBLIGATION/UNKNOWN) |
| `fixtures/ibk/README.md` | IBK 샘플 수급 지침 |
| `fixtures/laina/README.md` | 라이나 샘플 수급 지침 + 구조 변이 메모 |
| `tests/test_classifier.py` | 10개 smoke 테스트 (전부 통과 확인됨) |

**검증 결과**: `PYTHONPATH=src python -m pytest tests/ -v` → 10/10 PASSED (Python 3.13)

---

## 4. 아직 안 한 것 (Pending)

> 회귀 기준 변경 이력: `fixtures/ibk/expected.json`(ICR Java 파서 덤프) 방식은 폐기되고 `fixtures/ibk/expected.xlsx`(사용자 수동 작성본)로 전환됐으나, 수동 작성본이 DOCX 원문과 달리 법령/어미를 편집한 것으로 확인돼 **셀 단위 비교 대신 `DOCX 원본 ↔ 생성 XLSX` 왕복 검증**을 최종 회귀 기준으로 채택(2026-04-14).

### 4.1 사용자 측 (AI가 대신 못 함)

- [ ] **Phase 1 공식 종료 검증**: 생성된 `IBK_파이프라인_출력.xlsx`를 ICR Java 파서(`XlsxTemplateParserServiceImpl.java`)에 넣어 기존 결과와 글자 단위 동일 확인
- [ ] **라이나 HWP 샘플 배치**: `fixtures/laina/input.hwp` + 대응 정답 XLSX (있으면) 제공
- [ ] **외국인 임원명 사례 확인**: 현재 name 필드는 제약 없이 수용하지만 실측 안 됨 (HANDOFF §8)
- [ ] **`.hwp` vs `.hwpx` 비율 확인**: pyhwp는 `.hwp`만 지원 (HANDOFF §8 Gotcha #3)

### 4.2 AI 측

**Phase 1 (완료, 커밋 `2dc0d03`):**
- [x] `extractors/docx_extractor.py` — top-level 27개 테이블 + merged cell dedup + 단락별 bold 보존
- [x] `normalizer.py` — 9임원 그룹화, 라벨 기반 파싱, `등` 제거, 고유/공통 분류
- [x] `xlsx_writer.py` — 템플릿 복제, delta 기반 행 조정, 각주/헤더 보존, wrap_text + auto-fit
- [x] `tests/test_e2e_ibk.py` — DOCX 원본 기준 왕복 검증 11개 (expected.xlsx 비교 배제)

**Phase 1 사후 확장 (완료, 2026-04-14, 커밋 `519c7f2`):**
- [x] classifier 번호 체계 방어적 확장 — `①-⑳` 외에도 `⑴-⒇`/`⒈-⒛`/`1.`/`가.`/`Ⅰ.` 6종 인식
- [x] normalizer 3-mode 파서 — `bold`(IBK) / `tag`(라이나) / `number`(폴백)
- [x] `tests/test_obligation_variants.py` — 모드 감지·스플리터·통합 테스트 16개

**Phase 1.5 — 데스크톱 GUI + 배포 (완료, 2026-04-14, 커밋 `ad5c73b`):**
- [x] `src/chaekmu_parser_gui/` — customtkinter 기반 단일 파일 변환 GUI
  - `app.py` MainWindow, `workers.py` 백그라운드 스레드 + 큐 통신
  - `logging_setup.py` 일 단위 로그 + `friendly_error()` 한국어 오류 메시지
- [x] `build/gui.spec` + `scripts/build_exe.ps1` — PyInstaller --onedir 원샷 빌드
- [x] `docs/읽어보세요.txt` — 비개발자 배포용 SmartScreen 안내
- [x] 산출물: `dist/chaekmu-parser-v0.1.0-win64.zip` (17MB)
- [x] 설계 문서: `claudedocs/gui_packaging_design.md`

**Phase 2a — validator 3단계 정합성 검증 (완료, 2026-04-14, 커밋 `e6e2d76`):**
- [x] `src/chaekmu_parser/validator.py` — Stage 1 재추출 비교 / Stage 2 parsed→raw substring / Stage 3 SequenceMatcher quick_ratio
- [x] `ValidationReport` 자료구조 — 이슈 리스트 + 단계별 카운트 + `passed`/`has_warnings` 속성 + `summary_line()`
- [x] GUI 연동: 워커가 write 후 자동 호출 → 로그에 한 줄 요약 → `[🔍 검증 리포트]` 버튼 → `ReportWindow` Toplevel
- [x] `tests/test_validator.py` 9개 + `tests/test_gui_report_window.py` 2개, IBK 실측 통과 (Stage1 누락 < 1%, Stage2 verify ≥ 60, Stage3 ≈ 84%)

**Phase 2b — HWP (대기):**
- [ ] `extractors/hwp_extractor.py` — pyhwp 기반, 독립 회의체 테이블 지원. **라이나 fixture 제공 전까지 블록됨**
- [ ] `normalizer.py` 라이나 variant handler — 표 수 3→4 대응 (COMMITTEE 독립 테이블을 그룹화 로직에 흡수)
- [ ] `validator.py` Stage 1 HWP 경로 — 현재 docx만 지원 (`_extract_source_fragments`에서 `fmt == "docx"`만 분기)
- [ ] `tests/test_laina_e2e.py` — 라이나 HWP → XLSX 왕복 검증

**Phase 2 잔여 안전장치 (완료, 커밋 `cdf4fc0`):**
- [x] S1: `build/gui.spec` hiddenimports에 `chaekmu_parser.validator` 명시
- [x] S2: `xlsx_writer._adjust_block`의 `delete_at < 1 or >= footer_row` → `ValueError`
- [x] S3: `app.py` `self._report_window` 참조 관리 — 기존 창 살아있으면 lift/focus, 새 파이프라인 완료 시 이전 창 destroy
- [x] S4: `_open_in_file_manager()` — Win/macOS/Linux 플랫폼 분기 + 실패 시 로그만
- [x] S5: `_POLL_MAX_TICKS=3000` (5분) 폴링 타임아웃 + 안내 메시지
- [x] `tests/test_safety_guards.py` 4개 (S2/S4/S5 단위)

**Phase 3 (샘플 유입 시):**
- [ ] `extractors/pdf_extractor.py` — pdfplumber
- [ ] 신규 회사별 variant handler 추가 (Core 수정 금지)

---

## 5. 핵심 설계 결정 (불변)

### 5.1 Core vs Add-on 경계

```
Core (시드 2개로 확정, 이후 변경 없음)
├─ models.py              ← 인터페이스 불변
├─ extractors/base.py     ← 인터페이스 불변
├─ classifier.py          ← 법령 라벨 기반, 완화만 허용
├─ normalizer.py          ← 통일 JSON 스키마 불변
├─ validator.py           ← Phase 2a 구현 완료 (Stage 1은 docx 한정)
└─ xlsx_writer.py

Add-on (포맷/회사 추가 시 확장)
├─ extractors/docx_extractor.py  (Phase 1)
├─ extractors/hwp_extractor.py   (Phase 2)
├─ extractors/pdf_extractor.py   (Phase 3)
└─ normalizer 내부 variant handler 체인
```

**규칙**: 신규 회사 대응으로 Core 수정이 필요하면 설계 실패 신호. variant handler 추가로 해결해야 함.

### 5.2 라벨 기반 분류 (인덱스 의존 금지)

- 금융위 시행령 별표1이 강제하는 라벨(`직책`/`성명`/`회의체명`/`책무 개요`/`<고유 책무>` 등)로 테이블 유형 판정
- 테이블 인덱스(`tables[3]` 등) 의존 금지 — 회사마다 인덱스 다름
- 매칭 실패(UNKNOWN) 시 예외 대신 리뷰 큐로

### 5.3 raw / parsed 분리

정합성 검증 위해 가공 전(raw 셀 텍스트)과 가공 후(parsed 필드)를 분리 저장.
`Responsibility.raw_law_reg`, `Responsibility.source(SourceRef)` 등.

### 5.4 3단계 정합성 검증 (Phase 2a 구현 완료)

`src/chaekmu_parser/validator.py` — `validate(parsed, raw, source_path)` → `ValidationReport`.

1. **Stage 1** raw ↔ 원본 파일 재추출 글자 단위 비교 (현재 docx만 지원, HWP/PDF는 Phase 2b/3 확장)
2. **Stage 2** parsed 조각이 raw에 substring으로 존재 + 누락 탐지
3. **Stage 3** parsed 역재조립 후 raw와 `SequenceMatcher.quick_ratio()` 유사도 비교

**임계치** (validator.py 상단 상수):
- Stage 1 누락률: 1% 경고 / 5% 오류
- Stage 3 유사도: 55% 경고 / 30% 오류 (IBK 기준 84% 통과)

GUI는 워커가 write 후 자동 호출 → `🔍 요약 라인` 로그 출력 → `[검증 리포트]` 버튼으로 `ReportWindow` 상세 뷰.

---

## 6. 기각된 접근 (재탐색 금지)

| 접근 | 기각 이유 | 출처 |
|---|---|---|
| LLM 기반 추출 (Claude API) | 법령명 축약/환각 검증 불가. 금융 규제 문서 특성상 부적합 | 분석문서 §12 |
| HWP → DOCX 변환 (LibreOffice 등) | 표 구조 파괴됨. pyhwp 네이티브가 정답 | 분석문서 §11 |
| HWP → PDF → pdfplumber | 셀 내 레이아웃 줄바꿈 vs 의미 줄바꿈 구별 불가 | 분석문서 §10 |
| 테이블 인덱스 기반 파싱 | 회사마다 인덱스 다름(IBK tables[0~2] vs 라이나 tables[3~6]) | 분석문서 §10 |
| 회사별 정규식 config (54개) | 공수 폭발, 양식 변경 시 전면 재작업 | 분석문서 §8 (기각) |
| 수동 XLSX 전처리 | 54개사 × 5~10임원 비현실적 | 분석문서 §7 |

---

## 7. 시드 2개 구조 변이 요약

| 항목 | IBK (DOCX) | 라이나 (HWP) |
|---|---|---|
| 임원 수 | 9명 | 17명 |
| 임원당 테이블 수 | 3개 | 4개 |
| 회의체 위치 | EXEC_INFO Row4 **중첩 테이블** | **독립 테이블** (별도) |
| 책무 열 수 | 4열 | 3열 |
| 관리의무 표기 | **bold 단락** = 제목 | **`<고유 책무>/<공통 책무>` 태그 + ①②③** 원숫자 |
| 관리의무 분류 | 마지막 블록=공통 (대표이사 제외) | 명시 태그 파싱 |

normalizer variant handler가 위 차이를 모두 흡수해야 함.

---

## 8. Gotchas (놓치기 쉬운 것)

1. **프로젝트 경로는 ASCII**: `C:\project\workspace\chaekmu-parser\` (한글 "책무기술서-parser" 아님 — Windows/CI 안정성)
2. **원본 파일 커밋 금지**: `.gitignore`에 `fixtures/*/input.*` 등재. 기밀/저작권 이슈
3. **`.hwp` 전용**: pyhwp는 `.hwpx` 미지원. 실측 시 비율 확인 필요 (미해결)
4. **영문 임원명**: 현재 name 정규식은 한글 2~5자. 외국인 임원 케이스는 아직 미처리 (미해결)
5. **분석문서 §8, §9 기각됨**: 상단 읽기 가이드 표에 표시됨. 기각 섹션은 이력 보존용이며 적용 금지
6. **Classifier `UNKNOWN`은 정상 출력**: 예외 던지지 말고 리뷰 큐 경로로
7. **Core 파일은 회사 추가로 수정 금지**: `classifier.py`는 완화(정규식 `\s*` 추가 등)만 허용

---

## 9. 참조 문서 (중요도 순)

### 9.1 프로젝트 외부 (Desktop)

| 경로 | 내용 | 언제 읽을지 |
|---|---|---|
| `C:\Users\uesr\Desktop\ICR 관련 MD\책무기술서_파이프라인_분석.md` | 전체 파이프라인 설계 (§12/§13 최종안) | 설계 결정 재확인 |
| `C:\Users\uesr\Desktop\ICR 관련 MD\라벨분류_정규식_명세_v0.1.md` | Classifier/Normalizer 규칙 명세 | 새 정규식 추가/수정 시 |

### 9.2 ICR 프로젝트 참조

| 경로 | 내용 | 언제 읽을지 |
|---|---|---|
| `C:\project\workspace\icr\src\main\java\kr\co\infodea\icr\service\common\impl\XlsxTemplateParserServiceImpl.java` | 최종 수신자(Java 파서). 출력 XLSX 포맷은 이 파서가 먹을 수 있어야 함 | XLSX writer 구현 시 |

### 9.3 본 프로젝트 내부

| 경로 | 내용 |
|---|---|
| `README.md` | 구조 개요, 확장 규칙 |
| `src/chaekmu_parser/models.py` | 출력 스키마 정답지 |
| `src/chaekmu_parser/classifier.py` | 현재 정규식 상태 (v0.1) |
| `tests/test_classifier.py` | 회귀 기준 smoke 테스트 |

---

## 10. 다음 세션 프롬프트 템플릿

```
C:\project\workspace\chaekmu-parser\HANDOFF.md 읽고 이어서 진행.
현재 Phase 1 스캐폴딩까지 완료됐고, fixture 준비 상태 먼저 확인해줘.
준비됐으면 DocxExtractor부터 구현 시작.
```

---

## 11. 마지막 세션 요약

### 2026-04-14 세션

**완료 — Phase 1 IBK DOCX→XLSX 파이프라인 E2E (커밋 `2dc0d03`):**
- Step A: 입력/출력 3자 구조 분석 → `claudedocs/ibk_field_mapping.md`
  - **핵심 발견**: 템플릿 `설정` 시트가 이미 완전한 매핑 스펙 문서
- DocxExtractor: 27 테이블, merged cell dedup (표A row 4 중첩표 3중 노출 해결), 단락별 bold 보존
- Normalizer: 3표 단위 임원 그룹화(인덱스 의존 없음), 라벨 기반 파싱, 법령 말미 ` 등` 제거, 공통/고유 분류
- xlsx_writer: 템플릿 복제 + delta 기반 행 조정, 버그 2종 수정 (각주 B열 보호 / 상위 섹션 삽입 후 하위 좌표 shift 누락)
- wrap_text + 행 높이 초기화로 Excel auto-fit 유도

**완료 — Phase 1 사후 확장 (커밋 `519c7f2`):**
- classifier `PATTERN_OBLIGATION_NUMBER` — `①` 외에 5종 추가 인식 (`⑴/⒈/1./가./Ⅰ.`)
- normalizer `_parse_obligation` → 3-mode auto-detect (`bold`/`tag`/`number`) + `_split_by_*` 스플리터 분리
- `_resolve_obligation_type` 우선순위 통합: CEO → 태그 → 위치·키워드 → 기본
- 테스트 16개 추가, 전체 59/59 통과

**완료 — Phase 1.5 데스크톱 GUI + 배포 (커밋 `ad5c73b`):**
- customtkinter 기반 `chaekmu_parser_gui/` 패키지 (app/workers/logging_setup + assets)
- `PipelineRequest` + `queue.Queue` 백그라운드 워커 패턴
- 일 단위 로그 로테이션(`%LOCALAPPDATA%`) + `friendly_error()` 한국어 오류 메시지
- PyInstaller `--onedir` 빌드 → **17MB zip** (목표 100~120MB 대비 압도적 절감)
- `docs/읽어보세요.txt` SmartScreen 안내 포함
- 전체 67/67 통과 (GUI 테스트 8 추가)
- 설계 문서: `claudedocs/gui_packaging_design.md` §11 확정 사항 기록

**완료 — Phase 2a validator 3단계 정합성 검증 (커밋 `e6e2d76`):**
- `src/chaekmu_parser/validator.py` — Stage 1 재추출 비교(docx), Stage 2 parsed→raw substring, Stage 3 quick_ratio 유사도
- `ValidationReport` + 단계별 카운트 + `summary_line()`
- GUI 연동: 워커가 write 후 자동 호출 → 로그 요약 → `[🔍 검증 리포트]` 버튼 → `ReportWindow` Toplevel
- IBK 실측: Stage1 누락 < 1%, Stage2 verify ≥ 60 (누락 0), Stage3 ≈ 84% (기준 55% 상회)
- 전체 78/78 통과

**완료 — Phase 2 착수 전 안전장치 S1~S5 (커밋 `cdf4fc0`):**
- S1 gui.spec validator hiddenimport / S2 xlsx delete_at 가드 / S3 ReportWindow 참조 관리 /
  S4 파일 탐색기 플랫폼 분기 / S5 폴링 5분 타임아웃
- 전체 83/83 통과, `dist/chaekmu-parser-v0.1.0-win64.zip` 재생성 (17MB 유지)

**결정:**
- **회귀 기준 변경**: `expected.xlsx`(사용자 수동 작성본)가 DOCX 원본에서 법령/어미를 편집한 것으로 확인 → **셀 단위 비교 배제**, **DOCX 원본 충실 반영**만 검증 (`test_e2e_ibk.py`)
- 관리의무 번호 체계 다양성(#미해결 질문 3번)은 **라이나 fixture 유입 전 방어적 확장으로 선반영** (사용자 승인)
- GUI: **customtkinter + PyInstaller --onedir** 채택. Streamlit/tkinter 기본/PyQt 기각
- 배포는 **1차: 사용자가 수동 전달용**, 추후 사용 확대되면 코드 서명 재검토
- Stage 3 유사도 임계치: **55% 경고 / 30% 오류** 유지 (IBK 84% 기준)

**대기:**
- 사용자: 라이나 HWP 샘플 파일 경로 + 포맷(.hwp/.hwpx) 확인
- Phase 1 공식 종료 조건(생성 XLSX를 ICR Java 파서에 실소비) 미검증
- Phase 2 잔여 안전장치 5개 (HANDOFF §4.2 "Phase 2 잔여 안전장치" 참고)

**다음 세션 진입 시:**
1. `HANDOFF.md` + `CLAUDE.md` 교차 확인
2. `git log --oneline -10`으로 최근 변경 확인
3. 안전장치 5개 처리 or Phase 2b HWP 진입 중 선택 (라이나 fixture 의존성 확인)

**결정:**
- **회귀 기준 변경**: `expected.xlsx`(사용자 수동 작성본)가 DOCX 원본에서 법령/어미를 편집한 것으로 확인 → **셀 단위 비교 배제**, **DOCX 원본 충실 반영**만 검증 (`test_e2e_ibk.py`)
- 관리의무 번호 체계 다양성(#미해결 질문 3번)은 **라이나 fixture 유입 전 방어적 확장으로 선반영** (사용자 승인)

**대기:**
- 사용자: 라이나 HWP 샘플 파일 경로 + 포맷(.hwp/.hwpx) 확인
- Phase 1 공식 종료 조건(생성 XLSX를 ICR Java 파서에 실소비) 미검증

**다음 세션 진입 시:**
1. `HANDOFF.md` + `CLAUDE.md` 교차 확인
2. §4.2 Phase 2 목록에서 착수 지점 선택
3. 라이나 fixture 준비되면 Step A 재실행(`scripts/dump_docx.py` 포맷 유사), 안 되어있으면 `validator.py` 선행 가능

---

### 2026-04-13 세션

**완료**:
- 설계 문서 2종 정리 (`책무기술서_파이프라인_분석.md` §8/§9 기각 배너, `라벨분류_정규식_명세_v0.1.md` 신규)
- `chaekmu-parser` 프로젝트 스캐폴딩 전체 생성
- Classifier 10개 테스트 전부 통과 (Python 3.13)

**결정**:
- 54개 샘플 실측 기다리지 않고 2개 시드로 Core 확정 후 add-on으로 확장
- 프로젝트 경로 ASCII (`chaekmu-parser`) 채택
- PDF 지원은 Phase 3으로 지연
