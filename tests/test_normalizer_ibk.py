"""Normalizer 검증 — 실 IBK fixture 기반."""

from pathlib import Path

import pytest

from chaekmu_parser.extractors.docx_extractor import DocxExtractor
from chaekmu_parser.normalizer import normalize

FIXTURE = Path(__file__).parent.parent / "fixtures/ibk/input.docx"
pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="IBK fixture not present"
)


@pytest.fixture(scope="module")
def parsed():
    raw = DocxExtractor().extract(FIXTURE)
    return normalize(raw)


def test_nine_executives(parsed):
    assert parsed.parse_info.executive_count == 9
    assert len(parsed.executives) == 9


def test_first_executive_is_ceo(parsed):
    e0 = parsed.executives[0]
    assert "대표이사" in e0.position
    assert e0.name == "전병성"
    assert e0.title == "대표이사"
    assert e0.appointed_date.startswith("2025")
    assert e0.concurrent_yn == "Y"
    assert e0.departments == "전 부서"


def test_ceo_all_obligations_are_gouyou(parsed):
    """대표이사는 전부 고유 책무."""
    e0 = parsed.executives[0]
    assert len(e0.obligations) >= 1
    assert all(o.type == "고유 책무" for o in e0.obligations)


def test_non_ceo_last_obligation_is_common(parsed):
    """비대표이사 임원의 마지막 관리의무 블록은 공통책무."""
    non_ceos = [e for e in parsed.executives if "대표이사" not in e.position]
    assert non_ceos, "비대표이사 임원이 있어야 함"
    for e in non_ceos:
        if not e.obligations:
            continue
        types = [o.type for o in e.obligations]
        # 마지막 블록이 공통책무 조건에 부합하면 공통으로 분류되어야 함
        last = e.obligations[-1]
        if "내부통제" in last.category and "관리조치" in last.category:
            assert last.type == "공통 책무", (
                f"{e.position}의 마지막 obligation이 공통책무로 분류되어야 함"
            )
            # 앞 항목은 모두 고유
            assert all(t == "고유 책무" for t in types[:-1])


def test_marketing_committee_count_matches_expected(parsed):
    """마케팅본부장 회의체 = expected.xlsx 기준 7개."""
    marketing = next((e for e in parsed.executives if "마케팅" in e.position), None)
    assert marketing is not None
    assert len(marketing.committees) == 7
    # 첫 회의체 구조 검증
    c0 = marketing.committees[0]
    assert c0.name
    assert c0.role
    assert c0.cycle
    assert c0.matters


def test_responsibility_has_required_fields(parsed):
    e0 = parsed.executives[0]
    assert len(e0.responsibilities) >= 1
    r0 = e0.responsibilities[0]
    assert r0.category
    assert r0.details
    assert r0.raw_law_reg
    assert r0.source is not None


def test_trailing_deung_stripped_in_law_text(parsed):
    """법령 말미 ' 등' 제거 후처리 검증."""
    # 전체 임원에서 law 텍스트 수집
    all_law = "\n".join(
        r.raw_law_reg
        for e in parsed.executives
        for r in e.responsibilities
    )
    # 줄 말미 ' 등'으로 끝나는 라인이 없어야 함
    for line in all_law.split("\n"):
        assert not line.rstrip().endswith(" 등"), f"말미 ' 등' 미제거: {line!r}"


def test_resp_summary_and_assign_date_present(parsed):
    for e in parsed.executives:
        assert e.responsibility_summary, f"{e.position}: 책무 개요 누락"
        assert e.assign_date, f"{e.position}: 배분일자 누락"
