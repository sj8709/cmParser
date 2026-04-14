# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 본 저장소에서 작업할 때 참고할 지침을 제공합니다.

## 세션 진입점

**항상 `HANDOFF.md`를 먼저 읽을 것** — 세션 이어가기용 정본 문서입니다 (현재 Phase, Done/Pending, 기각된 접근, 마지막 세션 요약). `HANDOFF.md`의 "마지막 세션 요약"은 스냅샷이라 실제 코드 상태와 어긋날 수 있으므로, 구조 파악 후 반드시 `git log`/`git status`와 소스를 교차 확인할 것.

README는 짧은 개요. 설계 문서는 저장소 외부 `C:\Users\uesr\Desktop\ICR 관련 MD\` 에 위치:
- `책무기술서_파이프라인_분석.md` — 전체 파이프라인 설계 (§12/§13 최종안)
- `라벨분류_정규식_명세_v0.1.md` — classifier/normalizer 정규식 명세

저장소 내부 설계 기록:
- `claudedocs/ibk_field_mapping.md` — IBK DOCX 필드 매핑 레퍼런스
- `claudedocs/gui_packaging_design.md` — GUI/PyInstaller 설계 결정 기록

하류 Java 소비자: `C:\project\workspace\icr\src\main\java\kr\co\infodea\icr\service\common\impl\XlsxTemplateParserServiceImpl.java` — 본 프로젝트가 산출하는 XLSX는 이 파서가 먹을 수 있어야 합니다.

## 현재 진행 상태

| Phase | 범위 | 상태 |
|---|---|---|
| 1 | DOCX extractor + classifier + normalizer + xlsx_writer, IBK E2E | 완료 (`2dc0d03`) |
| 1.5 | 관리의무 번호 체계 방어적 확장 (라이나 선반영) | 완료 (`519c7f2`) |
| 1.9 | 데스크톱 GUI(customtkinter) + PyInstaller 번들 | 완료 (`ad5c73b`) — `dist/chaekmu-parser-v0.1.0-win64.zip` 17MB |
| 2a | `validator.py` 3단계 검증 + GUI 리포트 뷰어 | 완료 (`e6e2d76`) — DOCX Stage 1 구현, HWP Stage 1은 Phase 2b에서 확장 |
| 2b | HWP extractor(pyhwp) + 라이나 E2E | 예정 |
| 3 | PDF extractor 및 신규 회사 add-on | 샘플 유입 시 |

## 패키지 2개 관계

```
src/chaekmu_parser/        ← 라이브러리 (Core + Add-on). 순수 파이프라인, UI 의존 없음
src/chaekmu_parser_gui/    ← 소비자. chaekmu_parser를 import만 하고 Tk UI/스레딩/로깅만 담당
```

**불변 규칙**: GUI는 core를 **import만** 한다. core 수정 이유가 GUI여선 안 됨. GUI는 언제든 제거/교체 가능한 얇은 래퍼여야 함.

## 명령어

```powershell
# 초기 세팅 (최초 1회) — dev/gui/build 중 필요한 것만 조합
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"              # 파이프라인 개발
pip install -e ".[dev,gui]"          # GUI까지 로컬 실행
pip install -e ".[dev,gui,build]"    # PyInstaller 번들까지

# 테스트 (pyproject가 pythonpath=src 설정, -e 설치 후엔 PYTHONPATH 불필요)
pytest                                        # 전체
pytest tests/test_classifier.py -v            # 분류기 smoke
pytest tests/test_docx_extractor.py -v        # DOCX 추출기
pytest tests/test_normalizer_ibk.py -v        # IBK normalizer 단위
pytest tests/test_obligation_variants.py -v   # 관리의무 파싱 3-모드 변이
pytest tests/test_validator.py -v             # 3단계 정합성 검증 단위
pytest tests/test_xlsx_writer_smoke.py        # XLSX writer smoke
pytest tests/test_e2e_ibk.py -v               # IBK 원본→XLSX E2E (fixtures/ibk/input.docx 필요)
pytest tests/test_gui_worker.py -v            # GUI 워커 스레드 E2E (검증 리포트 포함)
pytest tests/test_gui_logging.py -v           # GUI 파일 로깅
pytest tests/test_gui_report_window.py -v     # 검증 리포트 Toplevel
pytest tests/test_e2e_ibk.py::test_name       # 단일 테스트

# 파이프라인 1회 실행 (IBK fixture → ~/Desktop/IBK_파이프라인_출력.xlsx)
python scripts/run_pipeline.py

# GUI 실행 (개발 환경)
chaekmu-parser-gui
# 또는: python -m chaekmu_parser_gui

# 실행 파일 빌드 (PyInstaller --onedir + zip 원샷)
pwsh scripts/build_exe.ps1
# → dist/chaekmu-parser/ + dist/chaekmu-parser-v<ver>-win64.zip

# 디버깅용 덤프
python scripts/dump_docx.py               # DOCX 원본 구조
python scripts/dump_xlsx.py               # XLSX 출력 검수
# scripts/debug_*.py 는 .gitignore됨 (1회용 애드혹 스크립트 관례)
```

Python 3.10 이상 필요. Windows 환경 기준이며, Claude Code에서 도구 호출 시엔 Unix 스타일 경로를 쓸 것.

## 아키텍처

파이프라인: `DOCX/HWP/PDF → Extractor → RawDocument → classify_all → normalize → ParsedDocument → xlsx_writer → XLSX`.

**2계층 데이터 모델** (`src/chaekmu_parser/models.py`) — 이 분리는 Phase 2의 3단계 정합성 검증을 위해 존재:
- **Raw 계층** (`RawDocument`/`RawTable`/`RawCell`): extractor 출력. 원본 구조·중첩 테이블·문단별 `is_bold` 플래그를 보존. 가공 금지.
- **Parsed 계층** (`ParsedDocument`/`Executive`/`Responsibility`/`Obligation`): normalizer 출력. Java 파서의 JSON 구조와 동일. 각 parsed 항목은 raw 좌표를 가리키는 `SourceRef`를 함께 보관.

**Core vs Add-on 경계** (HANDOFF §5.1에서 강제):
- **Core** (시드 2개 기준으로 인터페이스 확정; 신규 회사 대응을 이유로 절대 변경 금지): `models.py`, `extractors/base.py`, `classifier.py`, `normalizer.py`(공개 구조), `xlsx_writer.py`.
- **Add-on** (신규 회사/포맷 추가 지점): `extractors/*_extractor.py` 신규 구현체 (`BaseExtractor` 구현), 또는 `normalizer.py` 내부 variant handler 추가.
- 신규 회사 때문에 Core 수정이 필요해 보이면 그건 설계 실패 신호 — variant handler로 풀어야 함. `classifier.py` 정규식은 *완화*(예: `\s*` 추가, 번호 체계 확장)만 허용, 구조 개편 금지.

**인덱스가 아닌 라벨 기반 분류.** `classifier.py`는 금융위 시행령 별표1이 강제하는 라벨(`직책`, `성명`, `책무 개요`, `<고유 책무>` 등)로 테이블 유형(`EXEC_INFO`/`COMMITTEE`/`RESP`/`OBLIGATION`/`UNKNOWN`)을 판정. 위치 인덱스 접근 절대 금지 — IBK와 라이나의 레이아웃이 다름 (IBK `tables[0..2]`, 라이나 `tables[3..6]`). `UNKNOWN`은 정상 출력 → 리뷰 큐로 라우팅, 예외 던지지 말 것.

**`normalizer.py`의 임원 그룹화**: 분류된 테이블 리스트를 훑으며 각 `EXEC_INFO` 뒤에 오는 `RESP`, `OBLIGATION`을 한 임원으로 묶음. 순수하게 타입 기반, 인덱스 연산 없음.

**관리의무 파싱은 3-모드 auto-detect** (`_detect_obligation_mode`):
1. `bold` — bold 문단 존재 시 제목/세부로 분리 (IBK 스타일)
2. `tag` — `<고유 책무>`/`<공통 책무>` 태그로 타입 명시 + 번호 접두어로 항목 분리 (라이나 스타일)
3. `number` — 번호 접두어만 있을 때 폴백 (신규 회사용 선반영)

우선순위 bold > tag > number. 타입 결정 순서: 대표이사=무조건 고유 → 태그 명시 타입 → 마지막 블록+공통책무 키워드 → 기본 고유. 변이 회귀는 `tests/test_obligation_variants.py`.

**관리의무 번호 체계 지원** (`PATTERN_OBLIGATION_NUMBER` / `_NUMBER_PREFIX`): `①~⑳`, `⑴~⒇`, `⒈~⒛`, `1./1)`, `가./가)`, `Ⅰ./Ⅱ.` 모두 인식. 신규 체계 발견 시 이 패턴 2곳(classifier·normalizer) 동시 업데이트.

**3단계 정합성 검증** (`src/chaekmu_parser/validator.py`, HANDOFF §5.4 구현):
- **Stage 1** — 원본을 DocxExtractor와 *독립 경로*로 다시 훑어 얻은 단락 세트가 `RawDocument`에 있는지 확인. Extractor 누락 탐지. DOCX만 구현 — HWP/PDF는 `None` 반환하고 스킵. 임계치: 누락률 ≥1% 경고, ≥5% 오류.
- **Stage 2** — ParsedDocument의 verbatim 필드(이름/직위/회의체/책무 카테고리·세부/관리의무 items)가 raw blob에 substring으로 존재하는지 대조. `raw_law_reg`같이 후처리된 필드는 제외.
- **Stage 3** — raw blob과 parsed blob을 `SequenceMatcher.quick_ratio()`로 비교. 임계치: <50% 경고, <30% 오류. `quick_ratio`는 set-based 근사 (정확 ratio는 O(n²)라 대용량 부적합).
- **결과**: `ValidationReport`에 stage별 카운트 + `ValidationIssue` 리스트. `passed`/`has_warnings`/`summary_line()` 편의 프로퍼티.
- **Fail-soft**: 검증 실패해도 XLSX 저장은 유지. 실패 원인 전달이 우선.

**IBK vs 라이나 구조 변이 요약** (HANDOFF §7) — normalizer variant handler가 전부 흡수해야 함:
| 항목 | IBK (DOCX) | 라이나 (HWP) |
|---|---|---|
| 임원당 테이블 수 | 3개 | 4개 |
| 회의체 위치 | EXEC_INFO Row4 중첩 테이블 | 독립 테이블 |
| 관리의무 표기 | bold 단락 = 제목 | `<고유 책무>/<공통 책무>` 태그 + ①②③ |
| 공통책무 판정 규칙 | 마지막 블록 = 공통 (대표이사 예외) | 명시 태그 |
| 파싱 모드 | `bold` | `tag` |

## GUI 패키지 (`chaekmu_parser_gui`)

- **`app.py`** — customtkinter MainWindow. 입력/저장/실행/진행률/로그/결과폴더·로그파일·검증리포트 열기.
- **`workers.py`** — `threading.Thread` + `queue.Queue(StatusMessage)` 기반 백그라운드 파이프라인. 메인 UI 스레드는 `root.after(100, poll)`로 큐 polling. 워커 안에서 UI 조작 금지. `template_path()`는 PyInstaller `sys._MEIPASS` 번들 모드와 개발 모드 둘 다 커버. 최종 `StatusMessage("done", ...)`에 `validation_report` 동봉.
- **`report_window.py`** — `ValidationReport`를 표시하는 `CTkToplevel`. stage별 요약 + 이슈 상세 리스트. "검증 리포트" 버튼은 `done` 수신 + `validation_report is not None`일 때만 활성.
- **`logging_setup.py`** — `TimedRotatingFileHandler` 일 단위 7일 보관. 위치: Windows `%LOCALAPPDATA%\chaekmu-parser\logs\YYYY-MM-DD.log` / 그 외 `~/.chaekmu-parser/chaekmu-parser/logs/`. 사용자에겐 traceback 대신 `friendly_error()`로 한국어 안내만 노출.
- **출력 파일명 규칙**: `<입력 stem>_output_<YYYYMMDD>.xlsx` (`output_filename()`).
- **번들 최적화**: `build/gui.spec`의 `excludes=[pdfplumber, pdfminer, cryptography, PIL, pypdfium2, pytest]` — Phase 3(PDF) 전까지 번들 크기 절감. PDF extractor 추가 시 제거.

## 관례

- **프로젝트 경로는 ASCII**: `C:\project\workspace\chaekmu-parser` — 한글 이름 아님. 이름 변경 금지.
- **원본 파일은 gitignore 대상**: `fixtures/*/input.*` (DOCX/HWP/PDF/XLSX). 기밀/저작권 이슈로 절대 커밋 금지.
- **pyhwp 제약**: `.hwp`만 지원 (`.hwpx` 미지원). HWP→DOCX/PDF 변환은 명시적으로 기각됨 (HANDOFF §6).
- **LLM 기반 추출은 본 파이프라인에서 기각** (규제 문서 정확도 요구사항) — 제안하지 말 것.
- **Extractor는 문단별 `is_bold`를 반드시 보존**할 것 — IBK 스타일 관리의무 파싱이 이에 의존.
- **GUI는 core를 import만** — GUI 대응으로 core를 수정해야 할 일이 생기면 해당 변경의 정당성을 core 요구사항으로 독립 증명할 것.
- **외국인 임원명 미검증**: HANDOFF §8 오픈 이슈. 현재 `name` 필드는 규제 없이 셀 값을 그대로 수용하지만 실측 안 됨.

## Git 커밋 규칙

- **`Co-Authored-By: Claude ...` 트레일러 넣지 말 것**. 🤖 Generated with Claude Code 푸터도 금지. 커밋 메시지는 본문만.
