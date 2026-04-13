"""classifier의 라벨 기반 분류 - 시드 2개 기준 smoke test."""

from chaekmu_parser.classifier import classify_table
from chaekmu_parser.models import RawCell, RawRow, RawTable


def _table(rows: list[list[str | RawCell]], index: int = 0) -> RawTable:
    built = []
    for row in rows:
        cells = [c if isinstance(c, RawCell) else RawCell(text=c) for c in row]
        built.append(RawRow(cells=cells))
    return RawTable(rows=built, source_index=index)


def test_exec_info_by_position_label():
    t = _table([["직책", "대표이사", "성명", "전병성"]])
    assert classify_table(t) == "EXEC_INFO"


def test_exec_info_with_spaces():
    t = _table([["직  책 ", "대표이사", "성  명", "전병성"]])
    assert classify_table(t) == "EXEC_INFO"


def test_committee_by_header_combination():
    t = _table([["회의체명", "위원장/위원", "개최주기", "주요 심의·의결사항"]])
    assert classify_table(t) == "COMMITTEE"


def test_resp_by_assign_date_label():
    t = _table([["책무 개요", "", "", "책무 배분일자"]])
    assert classify_table(t) == "RESP"


def test_resp_by_detail_header():
    t = _table([["책무", "책무 세부내용", "관련 법령 및 내규", ""]])
    assert classify_table(t) == "RESP"


def test_obligation_by_tag():
    t = _table([[RawCell(text="<고유 책무> 내부통제등의 전반적 집행...")]])
    assert classify_table(t) == "OBLIGATION"


def test_obligation_by_circled_number():
    t = _table([[RawCell(text="① 이사회에서 수립한 ...\n② 임직원이 ...")]])
    assert classify_table(t) == "OBLIGATION"


def test_obligation_by_bold():
    t = _table([[RawCell(text="내부통제등의 전반적 집행...", is_bold=True)]])
    assert classify_table(t) == "OBLIGATION"


def test_unknown_for_empty():
    t = _table([[""]])
    assert classify_table(t) == "UNKNOWN"


def test_unknown_for_unrelated_label():
    t = _table([["기타정보", "값"]])
    assert classify_table(t) == "UNKNOWN"
