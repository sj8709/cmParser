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

### 4.1 사용자 측 (AI가 대신 못 함)

- [ ] `fixtures/ibk/input.docx` 배치 (IBK 원본 DOCX 복사)
- [ ] `fixtures/ibk/expected.json` 생성 (기존 ICR Java 파서로 동일 DOCX 처리 후 JSON 덤프 → 회귀 기준)
- [ ] venv 생성 + deps 설치
  ```
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -e ".[dev]"
  ```

### 4.2 AI 측 (fixture 준비되면 즉시 시작)

- [ ] `extractors/docx_extractor.py` — python-docx 기반, 중첩 테이블/bold 보존
- [ ] `normalizer.py` — RawDocument → ParsedDocument (IBK 케이스 variant handler 3종)
- [ ] `xlsx_writer.py` — ParsedDocument → XLSX 템플릿 (openpyxl)
- [ ] `tests/test_ibk_e2e.py` — fixture 기반 회귀 테스트
- [ ] Phase 1 종료 조건: IBK DOCX → 생성된 XLSX를 ICR Java 파서에 넣어 기존 결과와 글자 단위 동일 확인

---

## 5. 핵심 설계 결정 (불변)

### 5.1 Core vs Add-on 경계

```
Core (시드 2개로 확정, 이후 변경 없음)
├─ models.py              ← 인터페이스 불변
├─ extractors/base.py     ← 인터페이스 불변
├─ classifier.py          ← 법령 라벨 기반, 완화만 허용
├─ normalizer.py          ← 통일 JSON 스키마 불변
├─ validator.py (Phase 2)
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

### 5.4 3단계 정합성 검증 (Phase 2에서 구현)

1. raw ↔ 원본 파일 재추출 글자 단위 비교
2. parsed 조각이 raw에 substring으로 존재 + 누락 탐지
3. parsed 역재조립 후 raw와 유사도 비교

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

### 2026-04-13 세션

**완료**:
- 설계 문서 2종 정리
  - `책무기술서_파이프라인_분석.md`: 상단 읽기 가이드 추가, §8/§9 기각 배너 강화
  - `라벨분류_정규식_명세_v0.1.md` 신규 작성 (시드 2개 기준)
- `chaekmu-parser` 프로젝트 스캐폴딩 전체 생성
- Classifier 10개 테스트 전부 통과 (Python 3.13)

**결정**:
- 54개 샘플 실측 기다리지 않고 2개 시드로 Core 확정 후 add-on으로 확장 전략
- 프로젝트 경로 ASCII (`chaekmu-parser`) 채택
- PDF 지원은 Phase 3 (샘플 유입 시)로 지연

**대기**:
- 사용자: IBK DOCX 샘플 + expected.json + venv 세팅
- 준비 완료 신호 오면 DocxExtractor 구현 착수

**미해결 질문 (파일럿 전)**:
- `.hwp`/`.hwpx` 비율
- 외국인 임원 이름 표기
- 관리의무 번호 체계 (①②③ 외 `1.`, `가.` 등 존재 가능)
