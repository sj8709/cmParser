"""validator.py — 3단계 정합성 검증 테스트."""

from copy import deepcopy
from pathlib import Path

import pytest

from chaekmu_parser.extractors.docx_extractor import DocxExtractor
from chaekmu_parser.models import (
    Executive,
    Footnotes,
    Obligation,
    ParsedDocument,
    ParseInfo,
    RawCell,
    RawDocument,
    RawParagraph,
    RawRow,
    RawTable,
    Responsibility,
)
from chaekmu_parser.normalizer import normalize
from chaekmu_parser.validator import (
    ValidationIssue,
    ValidationReport,
    validate,
)

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "fixtures/ibk/input.docx"


# ---------------------------------------------------------------------------
# 단위 — 가짜 입력으로 리포트 구조 검증
# ---------------------------------------------------------------------------
def _minimal_parsed() -> ParsedDocument:
    return ParsedDocument(
        executives=[
            Executive(
                id="e1", position="대표이사", name="홍길동", title="대표이사",
                appointed_date="2025. 01. 01.", concurrent_yn="N",
                concurrent_detail="N/A", departments="전 부서",
                committees=[],
                responsibility_summary="소관 업무 내부통제 총괄",
                assign_date="2025. 01. 01.",
                responsibilities=[
                    Responsibility(
                        category="내부통제 총괄 책무",
                        details=["내부통제등의 전반적 집행 및 운영 책임"],
                        laws=[], regulations=[],
                        raw_law_reg="[법령] 지배구조법",
                    )
                ],
                obligations=[
                    Obligation(
                        type="고유 책무",
                        category="내부통제 총괄 책임",
                        items=["각 임원 관리의무 이행 점검"],
                    ),
                ],
                footnotes=Footnotes(),
            )
        ],
        parse_info=ParseInfo(
            file_name="t.docx", total_pages=0, executive_count=1, parse_date="2026-04-14",
        ),
    )


def _raw_with(contents: list[str]) -> RawDocument:
    rows = [RawRow(cells=[RawCell(text=c, paragraphs=[RawParagraph(text=c)])]) for c in contents]
    return RawDocument(
        source_path="t.docx", format="docx",
        tables=[RawTable(rows=rows, source_index=0)],
        paragraphs=[],
    )


def test_report_passed_and_summary():
    parsed = _minimal_parsed()
    # raw에 parsed의 verbatim 필드들을 모두 포함시켜 Stage 2 통과
    raw = _raw_with([
        "대표이사", "홍길동", "대표이사", "2025. 01. 01.", "N", "N/A", "전 부서",
        "내부통제 총괄 책무", "내부통제등의 전반적 집행 및 운영 책임",
        "내부통제 총괄 책임", "각 임원 관리의무 이행 점검",
    ])
    report = validate(parsed, raw, source_path=None)
    assert report.passed
    assert report.stage2_verified_count >= 5
    assert report.stage2_missing_count == 0
    assert "통과" in report.summary_line()


def test_stage2_detects_missing_parsed_values():
    parsed = _minimal_parsed()
    raw = _raw_with(["전혀 관계없는 내용만 담은 raw"])
    report = validate(parsed, raw, source_path=None)
    assert report.stage2_missing_count > 0
    # 최소 하나의 warning 발생
    assert any(i.stage == 2 and i.severity == "warn" for i in report.issues)


def test_stage3_similarity_bounds():
    parsed = _minimal_parsed()
    raw = _raw_with(["대표이사", "홍길동"])
    report = validate(parsed, raw, source_path=None)
    assert 0.0 <= report.stage3_similarity <= 1.0


def test_stage1_skipped_when_no_source_path():
    parsed = _minimal_parsed()
    raw = _raw_with(["x"])
    report = validate(parsed, raw, source_path=None)
    # source_path 없으면 Stage 1 수행 안 함
    assert report.stage1_source_fragments == 0
    assert report.stage1_missing_fragments == 0


def test_counts_by_severity():
    issues = [
        ValidationIssue(1, "warn", "a"),
        ValidationIssue(2, "warn", "b"),
        ValidationIssue(3, "error", "c"),
    ]
    r = ValidationReport(issues=issues)
    counts = r.counts_by_severity()
    assert counts["warn"] == 2
    assert counts["error"] == 1
    assert not r.passed


# ---------------------------------------------------------------------------
# E2E — 실제 IBK fixture로 Stage 1/2/3 통과 확인
# ---------------------------------------------------------------------------
ibk_only = pytest.mark.skipif(not FIXTURE.exists(), reason="IBK fixture 없음")


@pytest.fixture(scope="module")
def ibk():
    raw = DocxExtractor().extract(FIXTURE)
    parsed = normalize(raw)
    return raw, parsed


@ibk_only
def test_ibk_validates_without_errors(ibk):
    raw, parsed = ibk
    report = validate(parsed, raw, source_path=FIXTURE)
    # 오류 없어야 함 (경고는 허용 — 법령 '등' 제거 후처리 제외 필드만 검사하므로 대부분 통과 예상)
    assert report.passed, (
        f"IBK 파이프라인 검증 실패: {report.summary_line()}\n"
        + "\n".join(f"  - [{i.stage}] {i.severity}: {i.message}" for i in report.issues)
    )


@ibk_only
def test_ibk_stage1_captures_most_source_fragments(ibk):
    raw, parsed = ibk
    report = validate(parsed, raw, source_path=FIXTURE)
    # 원본의 99% 이상은 raw에 담겨야 함 (stage 1 경고 기준)
    if report.stage1_source_fragments:
        miss_ratio = report.stage1_missing_fragments / report.stage1_source_fragments
        assert miss_ratio < 0.01, f"Stage 1 누락률 {miss_ratio:.2%}"


@ibk_only
def test_ibk_stage2_verification_count_high(ibk):
    raw, parsed = ibk
    report = validate(parsed, raw, source_path=FIXTURE)
    # 9 임원 × 평균 7~8 필드 = 최소 60개 이상 verify 되어야 함
    assert report.stage2_verified_count >= 60
    # 누락은 전체의 3% 이하
    total = report.stage2_verified_count + report.stage2_missing_count
    if total:
        assert report.stage2_missing_count / total < 0.03, (
            f"Stage 2 누락 비율 과다: {report.stage2_missing_count}/{total}"
        )


@ibk_only
def test_ibk_stage3_similarity_reasonable(ibk):
    raw, parsed = ibk
    report = validate(parsed, raw, source_path=FIXTURE)
    # IBK는 raw의 대부분을 parsed로 재조립하므로 유사도는 높아야 함
    assert report.stage3_similarity > _STAGE3_SIMILARITY_WARN_FOR_TEST, (
        f"Stage 3 유사도 낮음: {report.stage3_similarity:.2%}"
    )


# 테스트 상수 — validator의 _STAGE3_SIMILARITY_WARN과 별개로 테스트 기준 완화값
_STAGE3_SIMILARITY_WARN_FOR_TEST = 0.55
