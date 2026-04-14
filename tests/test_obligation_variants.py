"""관리의무 번호 체계 방어적 확장 — 3번째 회사 대비 회귀."""

from chaekmu_parser.classifier import classify_table
from chaekmu_parser.models import RawCell, RawParagraph, RawRow, RawTable
from chaekmu_parser.normalizer import (
    _detect_obligation_mode,
    _parse_obligation,
    _split_by_bold,
    _split_by_number,
    _split_by_tag,
)


def _cell(paragraphs: list[tuple[str, bool]]) -> RawCell:
    paras = [RawParagraph(text=t, is_bold=b) for t, b in paragraphs]
    joined = "\n".join(t for t, _ in paragraphs)
    any_bold = any(b for _, b in paragraphs)
    return RawCell(text=joined, is_bold=any_bold, paragraphs=paras)


def _table_1x1(paragraphs: list[tuple[str, bool]]) -> RawTable:
    cell = _cell(paragraphs)
    return RawTable(rows=[RawRow(cells=[cell])], source_index=0)


# ---------------------------------------------------------------------------
# classifier — 새 번호 포맷이 OBLIGATION으로 판정되는가
# ---------------------------------------------------------------------------
def test_obligation_by_arabic_number_dot():
    t = _table_1x1([("1. 첫 번째 항목", False), ("2. 두 번째 항목", False)])
    assert classify_table(t) == "OBLIGATION"


def test_obligation_by_arabic_number_paren():
    t = _table_1x1([("1) 첫 번째", False), ("2) 두 번째", False)])
    assert classify_table(t) == "OBLIGATION"


def test_obligation_by_hangul_jamo_dot():
    t = _table_1x1([("가. 첫 번째", False), ("나. 두 번째", False)])
    assert classify_table(t) == "OBLIGATION"


def test_obligation_by_parenthesized_number():
    t = _table_1x1([("⑴ 첫 번째", False), ("⑵ 두 번째", False)])
    assert classify_table(t) == "OBLIGATION"


def test_obligation_by_dotted_number():
    t = _table_1x1([("⒈ 첫 번째", False), ("⒉ 두 번째", False)])
    assert classify_table(t) == "OBLIGATION"


def test_obligation_by_roman_numeral():
    t = _table_1x1([("Ⅰ. 첫 번째", False), ("Ⅱ. 두 번째", False)])
    assert classify_table(t) == "OBLIGATION"


def test_no_false_positive_for_plain_text():
    """1x1이어도 번호 없는 평문은 obligation이 아님."""
    t = _table_1x1([("그냥 설명 텍스트입니다", False)])
    # bold 아니고 태그 없고 번호 없으므로 UNKNOWN
    assert classify_table(t) == "UNKNOWN"


# ---------------------------------------------------------------------------
# normalizer — 모드 감지 우선순위
# ---------------------------------------------------------------------------
def test_mode_bold_wins_over_others():
    cell = _cell([("제목", True), ("1. 세부", False)])
    assert _detect_obligation_mode(cell) == "bold"


def test_mode_tag_detected_when_no_bold():
    cell = _cell([("<고유 책무>", False), ("① 항목", False)])
    assert _detect_obligation_mode(cell) == "tag"


def test_mode_number_detected_as_fallback():
    cell = _cell([("1. 첫째", False), ("2. 둘째", False)])
    assert _detect_obligation_mode(cell) == "number"


# ---------------------------------------------------------------------------
# normalizer — 스플리터 동작
# ---------------------------------------------------------------------------
def test_split_by_bold_preserves_title_and_items():
    paras = [
        RawParagraph(text="책임A", is_bold=True),
        RawParagraph(text="세부A-1", is_bold=False),
        RawParagraph(text="세부A-2", is_bold=False),
        RawParagraph(text="책임B", is_bold=True),
        RawParagraph(text="세부B-1", is_bold=False),
    ]
    blocks = _split_by_bold(paras)
    assert len(blocks) == 2
    assert blocks[0] == (None, "책임A", ["세부A-1", "세부A-2"])
    assert blocks[1] == (None, "책임B", ["세부B-1"])


def test_split_by_tag_uses_explicit_type_and_number_items():
    paras = [
        RawParagraph(text="<고유 책무>"),
        RawParagraph(text="① 이사회 운영"),
        RawParagraph(text="② 감사 업무"),
        RawParagraph(text="<공통 책무>"),
        RawParagraph(text="① 내부통제 수립"),
    ]
    blocks = _split_by_tag(paras)
    assert len(blocks) == 3
    assert blocks[0] == ("고유 책무", "이사회 운영", [])
    assert blocks[1] == ("고유 책무", "감사 업무", [])
    assert blocks[2] == ("공통 책무", "내부통제 수립", [])


def test_split_by_number_falls_back_without_tags():
    paras = [
        RawParagraph(text="1. 첫 항목"),
        RawParagraph(text="부연 설명"),
        RawParagraph(text="2. 둘째 항목"),
    ]
    blocks = _split_by_number(paras)
    assert len(blocks) == 2
    assert blocks[0] == (None, "첫 항목", ["부연 설명"])
    assert blocks[1] == (None, "둘째 항목", [])


# ---------------------------------------------------------------------------
# 통합: _parse_obligation 모드별 동작
# ---------------------------------------------------------------------------
def test_parse_obligation_tag_mode_classifies_by_tag_not_position():
    """태그 모드: 위치와 무관하게 태그 타입 그대로."""
    t = _table_1x1([
        ("<공통 책무>", False),   # 일부러 맨 앞에 공통 태그
        ("① 첫째 항목", False),
        ("<고유 책무>", False),
        ("① 둘째 항목", False),
    ])
    obligations = _parse_obligation(t, position="마케팅본부장", table_index=0)
    assert len(obligations) == 2
    assert obligations[0].type == "공통 책무"
    assert obligations[1].type == "고유 책무"


def test_parse_obligation_ceo_overrides_tag():
    """대표이사는 태그가 공통책무여도 고유로 강제."""
    t = _table_1x1([
        ("<공통 책무>", False),
        ("① 어떤 항목", False),
    ])
    obligations = _parse_obligation(t, position="대표이사", table_index=0)
    assert len(obligations) == 1
    assert obligations[0].type == "고유 책무"


def test_parse_obligation_number_mode_uses_position_classification():
    """번호 모드 + 마지막 블록 키워드 → 공통책무."""
    t = _table_1x1([
        ("1. 이사회 운영 업무", False),
        ("2. 소관 조직의 내부통제등 관리조치의 수립·운영 및 이행에 대한 책임", False),
    ])
    obligations = _parse_obligation(t, position="본부장", table_index=0)
    assert len(obligations) == 2
    assert obligations[0].type == "고유 책무"
    assert obligations[1].type == "공통 책무"
