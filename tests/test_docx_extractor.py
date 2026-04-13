"""DocxExtractor 스모크 테스트 — IBK 실 fixture 기반."""

from pathlib import Path

import pytest

from chaekmu_parser.classifier import classify_all
from chaekmu_parser.extractors.docx_extractor import DocxExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures/ibk/input.docx"
pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="IBK fixture not present"
)


def test_extract_returns_expected_shape():
    doc = DocxExtractor().extract(FIXTURE)
    assert doc.format == "docx"
    assert doc.source_path.endswith("input.docx")
    # IBK: 9 임원 × 3 표
    assert len(doc.tables) == 27


def test_first_table_is_exec_info_with_footnote_label():
    doc = DocxExtractor().extract(FIXTURE)
    t0 = doc.tables[0]
    # 5행 × 4열
    assert len(t0.rows) == 5
    assert len(t0.rows[0].cells) == 4
    # cell(0,0) = '직책1)' (각주 번호 포함)
    assert "직책" in t0.rows[0].cells[0].text


def test_exec_info_row4_nested_committee_table_deduped():
    doc = DocxExtractor().extract(FIXTURE)
    t0 = doc.tables[0]
    row4 = t0.rows[4]
    # merged cell dedup 후 2개 셀 (라벨 + 병합된 값 영역)
    assert len(row4.cells) == 2
    # 두 번째 셀에 중첩 테이블 1개
    value_cell = row4.cells[1]
    assert len(value_cell.nested_tables) == 1
    nested = value_cell.nested_tables[0]
    # 헤더 + 최소 1행
    assert len(nested.rows) >= 2
    header = [c.text for c in nested.rows[0].cells]
    assert "회의체명" in header[0]


def test_obligation_block_has_mixed_bold_paragraphs():
    doc = DocxExtractor().extract(FIXTURE)
    # 표C는 1x1. 3번째 테이블(source_index=2).
    t2 = doc.tables[2]
    assert len(t2.rows) == 1
    assert len(t2.rows[0].cells) == 1
    cell = t2.rows[0].cells[0]
    bold_paras = [p for p in cell.paragraphs if p.is_bold and p.text.strip()]
    nonbold = [p for p in cell.paragraphs if not p.is_bold and p.text.strip()]
    assert bold_paras, "표C에 bold 단락(책무명 제목)이 있어야 함"
    assert nonbold, "표C에 non-bold 단락(세부 항목)이 있어야 함"


def test_all_27_tables_classified_as_expected_pattern():
    doc = DocxExtractor().extract(FIXTURE)
    classify_all(doc.tables)
    type_seq = [t.table_type for t in doc.tables]
    # 9회 반복 패턴: EXEC_INFO, RESP, OBLIGATION
    for i in range(9):
        assert type_seq[i * 3] == "EXEC_INFO", f"임원 {i+1} 표A"
        assert type_seq[i * 3 + 1] == "RESP", f"임원 {i+1} 표B"
        assert type_seq[i * 3 + 2] == "OBLIGATION", f"임원 {i+1} 표C"
