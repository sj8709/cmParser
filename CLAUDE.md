# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 본 저장소에서 작업할 때 참고할 지침을 제공합니다.

## 세션 진입점

**항상 `HANDOFF.md`를 먼저 읽을 것** — 세션 이어가기용 정본 문서입니다 (현재 Phase, Done/Pending, 기각된 접근, 마지막 세션 요약). `HANDOFF.md`의 "마지막 세션 요약"은 스냅샷이라 실제 코드 상태와 어긋날 수 있으므로, 구조 파악 후 반드시 `git log`/`git status`와 소스를 교차 확인할 것.

README는 짧은 개요. 설계 문서는 저장소 외부 `C:\Users\uesr\Desktop\ICR 관련 MD\` 에 위치:
- `책무기술서_파이프라인_분석.md` — 전체 파이프라인 설계 (§12/§13 최종안)
- `라벨분류_정규식_명세_v0.1.md` — classifier/normalizer 정규식 명세

하류 Java 소비자: `C:\project\workspace\icr\src\main\java\kr\co\infodea\icr\service\common\impl\XlsxTemplateParserServiceImpl.java` — 본 프로젝트가 산출하는 XLSX는 이 파서가 먹을 수 있어야 합니다.

## 현재 진행 상태

| Phase | 범위 | 상태 |
|---|---|---|
| 1 | DOCX extractor + classifier + normalizer + xlsx_writer, IBK E2E | 완료 (커밋 `2dc0d03`) |
| 2 | HWP extractor(pyhwp) + 3단계 검증, 라이나 E2E | 진행 중 — classifier/normalizer에 tag/number 모드 variant handler 선반영 (미커밋) |
| 3 | 신규 회사/PDF add-on | 샘플 유입 시 |

## 명령어

```powershell
# 초기 세팅 (최초 1회)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 테스트 (pyproject가 pythonpath=src 설정, -e 설치 후엔 PYTHONPATH 불필요)
pytest                                   # 전체
pytest tests/test_classifier.py -v       # 분류기 smoke
pytest tests/test_docx_extractor.py -v   # DOCX 추출기
pytest tests/test_normalizer_ibk.py -v   # IBK normalizer 단위
pytest tests/test_xlsx_writer_smoke.py   # XLSX writer smoke
pytest tests/test_e2e_ibk.py -v          # IBK 원본→XLSX E2E (fixtures/ibk/input.docx 필요)
pytest tests/test_e2e_ibk.py::test_name  # 단일 테스트

# 파이프라인 1회 실행 (IBK fixture → ~/Desktop/IBK_파이프라인_출력.xlsx)
python scripts/run_pipeline.py

# 디버깅용 덤프
python scripts/dump_docx.py               # DOCX 원본 구조
python scripts/dump_xlsx.py               # XLSX 출력 검수
python scripts/debug_marketing_gamsa.py   # 특정 임원(마케팅감사) 블록 디버깅
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

우선순위 bold > tag > number. 타입 결정 순서: 대표이사=무조건 고유 → 태그 명시 타입 → 마지막 블록+공통책무 키워드 → 기본 고유.

**관리의무 번호 체계 지원** (`PATTERN_OBLIGATION_NUMBER` / `_NUMBER_PREFIX`): `①~⑳`, `⑴~⒇`, `⒈~⒛`, `1./1)`, `가./가)`, `Ⅰ./Ⅱ.` 모두 인식. 신규 체계 발견 시 이 패턴 2곳(classifier·normalizer) 동시 업데이트.

**IBK vs 라이나 구조 변이 요약** (HANDOFF §7) — normalizer variant handler가 전부 흡수해야 함:
| 항목 | IBK (DOCX) | 라이나 (HWP) |
|---|---|---|
| 임원당 테이블 수 | 3개 | 4개 |
| 회의체 위치 | EXEC_INFO Row4 중첩 테이블 | 독립 테이블 |
| 관리의무 표기 | bold 단락 = 제목 | `<고유 책무>/<공통 책무>` 태그 + ①②③ |
| 공통책무 판정 규칙 | 마지막 블록 = 공통 (대표이사 예외) | 명시 태그 |
| 파싱 모드 | `bold` | `tag` |

## 관례

- **프로젝트 경로는 ASCII**: `C:\project\workspace\chaekmu-parser` — 한글 이름 아님. 이름 변경 금지.
- **원본 파일은 gitignore 대상**: `fixtures/*/input.*` (DOCX/HWP/PDF/XLSX). 기밀/저작권 이슈로 절대 커밋 금지.
- **pyhwp 제약**: `.hwp`만 지원 (`.hwpx` 미지원). HWP→DOCX/PDF 변환은 명시적으로 기각됨 (HANDOFF §6).
- **LLM 기반 추출은 본 파이프라인에서 기각** (규제 문서 정확도 요구사항) — 제안하지 말 것.
- **Extractor는 문단별 `is_bold`를 반드시 보존**할 것 — IBK 스타일 관리의무 파싱이 이에 의존.
- **외국인 임원명 미검증**: HANDOFF §8 오픈 이슈. 현재 `name` 필드는 규제 없이 셀 값을 그대로 수용하지만 실측 안 됨.

## Git 커밋 규칙

- **`Co-Authored-By: Claude ...` 트레일러 넣지 말 것**. 🤖 Generated with Claude Code 푸터도 금지. 커밋 메시지는 본문만.
