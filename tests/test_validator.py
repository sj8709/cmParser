"""validator.py — 5단계 정합성 검증 테스트."""

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
# Stage 4 — 구조 정합성 (책무세부 ↔ 관리의무 제목 대응)
# ---------------------------------------------------------------------------
def _exec(resp_details, obl_blocks, position="본부장"):
    """resp_details: list[str], obl_blocks: list[(category, items)]."""
    return Executive(
        id="e1", position=position, name="홍길동", title="본부장",
        appointed_date="", concurrent_yn="", concurrent_detail="", departments="",
        committees=[],
        responsibility_summary="", assign_date="",
        responsibilities=[
            Responsibility(category="책무", details=[d], laws=[], regulations=[])
            for d in resp_details
        ],
        obligations=[
            Obligation(type="고유 책무", category=c, items=list(items))
            for c, items in obl_blocks
        ],
        footnotes=Footnotes(),
    )


def _doc(*execs) -> ParsedDocument:
    return ParsedDocument(
        executives=list(execs),
        parse_info=ParseInfo("t.docx", 0, len(execs), "2026-05-26"),
    )


def test_stage4_flags_oversplit_obligation_title():
    """세부 0개 + 책무세부 미매칭 관리의무 제목 → 오추출 의심(warn). (KDB IT부문장 케이스)"""
    e = _exec(
        resp_details=["IT 표준·품질관리 및 IT 감리 운영에 대한 책임"],
        obl_blocks=[
            ("IT 표준·품질관리 및 IT 감리 운영에 대한 책임", ["IT 표준·아키텍처 관리"]),
            ("IT 감리 프로젝트 대상 내·외부 감리 업무", []),  # 오승격
        ],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_oversplit_count == 1
    assert report.stage4_missing_count == 0
    assert any(i.stage == 4 and i.severity == "warn" for i in report.issues)


def test_stage4_flags_source_missing_obligation():
    """대응 관리의무 없는 책무세부 → 원본 누락 추정(info). (IBK 동산/부동산 케이스)"""
    e = _exec(
        resp_details=[
            "전사 업무용 동산/업무용 부동산 관리 제반사항에 대한 책임",  # 누락
            "경비의 집행 및 관리에 대한 책임",
        ],
        obl_blocks=[
            ("경비의 집행 및 관리에 대한 책임", ["본부 경비의 집행에 대한 관리·감독"]),
        ],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_missing_count == 1
    assert report.stage4_oversplit_count == 0
    assert any(i.stage == 4 and i.severity == "info" for i in report.issues)
    # fail-soft: Stage 4는 error를 만들지 않음 (info/warn 뿐 → 저장 막지 않음)
    assert not any(i.stage == 4 and i.severity == "error" for i in report.issues)


def test_stage4_escalates_bulk_missing_to_warn():
    """한 임원에서 누락 추정이 임계치(3) 이상 → 집계 이슈 warn 승격.
    (라이나 2026-07: 자동번호 제목이 세부항목으로 흡수돼 임원당 4~10건씩 뭉텅이 누락)"""
    e = _exec(
        resp_details=[
            "소관 업무 관련 내부통제기준등의 집행·운영에 대한 책임",
            "소관 업무 관련 보고 및 공시에 대한 책임",
            "소관 업무 관련 시스템 개발·변경·운영 업무 지원에 대한 책임",
            "소관 업무 관련 위·수탁 계약 관리에 대한 책임",
        ],
        obl_blocks=[
            ("소관 업무 관련 내부통제기준등의 집행·운영에 대한 책임",
             ["소관 업무 관련 보고 및 공시 의무", "소관 업무 관련 위·수탁 계약 관리·감독 의무"]),
        ],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_missing_count == 3
    header = [i for i in report.issues if i.stage == 4 and "누락 추정" in i.message and "뭉텅이" in i.message]
    assert len(header) == 1 and header[0].severity == "warn"
    assert not any(i.stage == 4 and i.severity == "error" for i in report.issues)


def test_stage4_skips_tag_mode_all_empty_items():
    """관리의무 세부항목이 전부 0개(태그/번호 모드) → 검사 생략, 이슈 없음."""
    e = _exec(
        resp_details=["책무세부 가나다", "책무세부 라마바"],
        obl_blocks=[("이사회 운영", []), ("감사 업무", [])],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_oversplit_count == 0
    assert report.stage4_missing_count == 0
    assert not any(i.stage == 4 for i in report.issues)


def test_stage4_clean_when_titles_align():
    """책무세부와 관리의무 제목이 1:1로 맞으면 이슈 0."""
    e = _exec(
        resp_details=["책무세부 가나다라마", "책무세부 바사아자차"],
        obl_blocks=[
            ("책무세부 가나다라마", ["세부1"]),
            ("책무세부 바사아자차", ["세부2"]),
        ],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_oversplit_count == 0
    assert report.stage4_missing_count == 0


def test_stage4_tolerates_eomi_difference():
    """공통책무 어미 차이('관리책임' vs '관리에 대한 책임')는 누락으로 오탐하지 않음."""
    e = _exec(
        resp_details=["소관 업무·조직 내부통제정책 수립·운영 및 이행에 대한 내부통제등 관리책임"],
        obl_blocks=[
            ("소관 업무·조직 내부통제정책 수립·운영 및 이행에 대한 내부통제등 관리에 대한 책임",
             ["내부통제기준 마련 적정성 점검"]),
        ],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_missing_count == 0
    assert report.stage4_oversplit_count == 0
    # 어미 차이는 누락은 아니지만 '비동일'로 info 노출돼야 함 (ICR 정확 일치 조인 대상)
    assert report.stage4_nonidentical_count == 1
    assert any(
        i.stage == 4 and i.severity == "info" and "비동일" in i.message
        for i in report.issues
    )


def test_stage4_flags_nonidentical_wording():
    """대응되지만 원문 표현이 다른 책무세부↔관리의무 책무명 → 비동일(info). (KDB 퇴직연금 케이스)"""
    e = _exec(
        resp_details=["퇴직연금 상품 및 퇴직연금 사업 운영 및 관리에 대한 책임"],
        obl_blocks=[
            ("퇴직상품 및 퇴직연금 운영 및 관리에 대한 책임", ["퇴직연금 운영 관리·감독"]),
        ],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_nonidentical_count == 1
    assert report.stage4_missing_count == 0


def test_stage4_no_nonidentical_when_exact():
    """책무세부와 관리의무 책무명이 글자까지 동일하면 비동일 0."""
    e = _exec(
        resp_details=["보험상품 관련 개발·개선 절차 운영에 대한 책임"],
        obl_blocks=[
            ("보험상품 관련 개발·개선 절차 운영에 대한 책임", ["상품개발 절차 준수 관리·감독"]),
        ],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage4_nonidentical_count == 0


# ---------------------------------------------------------------------------
# Stage 5 — 공통/고유 정합성 (책무 '임원 공통' 표기 ↔ 공통 관리의무)
# ---------------------------------------------------------------------------
def _exec5(resp_categories, obl_types, position="본부장"):
    """resp_categories: list[str], obl_types: list[str] (관리의무 type 목록)."""
    return Executive(
        id="e1", position=position, name="홍길동", title="본부장",
        appointed_date="", concurrent_yn="", concurrent_detail="", departments="",
        committees=[],
        responsibility_summary="", assign_date="",
        responsibilities=[
            Responsibility(category=c, details=["세부"], laws=[], regulations=[])
            for c in resp_categories
        ],
        obligations=[
            Obligation(type=t, category="관리의무", items=["항목"])
            for t in obl_types
        ],
        footnotes=Footnotes(),
    )


def test_stage5_flags_common_misclassified():
    """책무에 '임원 공통' 표기가 있으나 관리의무가 전부 고유 → 공통 미분류 의심(warn)."""
    e = _exec5(
        resp_categories=["고유 책무", "소관 업무조직의 내부통제 관리에 대한 책무 (임원 공통)"],
        obl_types=["고유 책무", "고유 책무"],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage5_common_mismatch_count == 1
    assert any(i.stage == 5 and i.severity == "warn" for i in report.issues)


def test_stage5_flags_common_without_marker():
    """관리의무에 공통 책무가 있으나 책무엔 '임원 공통' 표기 없음 → 확인 권장(info)."""
    e = _exec5(
        resp_categories=["고유 책무 가나다"],
        obl_types=["고유 책무", "공통 책무"],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage5_common_mismatch_count == 1
    assert any(i.stage == 5 and i.severity == "info" for i in report.issues)


def test_stage5_clean_when_aligned():
    """'임원 공통' 표기 + 공통 관리의무가 함께 있으면 정합 → 이슈 0."""
    e = _exec5(
        resp_categories=["고유 책무", "소관 ... 책무(임원 공통)"],
        obl_types=["고유 책무", "공통 책무"],
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage5_common_mismatch_count == 0
    assert not any(i.stage == 5 for i in report.issues)


def test_stage5_clean_for_ceo_without_common():
    """대표이사처럼 책무·관리의무 모두 공통이 없으면 정상 통과."""
    e = _exec5(
        resp_categories=["내부통제 총괄 책무"],
        obl_types=["고유 책무"],
        position="대표이사",
    )
    report = validate(_doc(e), _raw_with(["dummy"]), source_path=None)
    assert report.stage5_common_mismatch_count == 0
    assert not any(i.stage == 5 for i in report.issues)


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
