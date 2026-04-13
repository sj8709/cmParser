"""
RawDocument → ParsedDocument.

책임:
  1. 3표 단위(EXEC_INFO + RESP + OBLIGATION)로 임원 그룹화 (인덱스 의존 X, 분류 타입만 사용)
  2. 표A → Executive 기본 필드 + Committee 리스트 (주관회의체 중첩표 파싱)
  3. 표B → responsibility_summary/assign_date + Responsibility 리스트
  4. 표C → Obligation 리스트 (bold=제목, non-bold=세부 items)
  5. 후처리: 법령/내규 말미 '등' 제거, 관리의무 고유/공통 분류 (대표이사 예외)
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from chaekmu_parser.classifier import (
    LABEL_APPT_DATE,
    LABEL_ASSIGN_DATE,
    LABEL_COMMITTEE_ROOT,
    LABEL_CONCUR_DTL,
    LABEL_CONCUR_YN,
    LABEL_DEPT,
    LABEL_NAME,
    LABEL_POSITION,
    LABEL_RESP_SUMMARY,
    LABEL_TITLE,
    PATTERN_RESP_DETAIL_COLS,
    PATTERN_RESP_HEADER,
    classify_all,
)
from chaekmu_parser.models import (
    Committee,
    Executive,
    Footnotes,
    Obligation,
    ObligationType,
    ParseInfo,
    ParsedDocument,
    RawCell,
    RawDocument,
    RawTable,
    Responsibility,
    SourceRef,
)

# '등' 제거 대상: 쉼표/공백 뒤 단독 '등' (말미)
_TRAILING_DEUNG = re.compile(r"(,\s*[^,\n]+?)\s+등(?=\s*$|\s*\n|\s*\|)", re.MULTILINE)
_CEO_PATTERN = re.compile(r"대\s*표\s*이\s*사")
_COMMON_OBLIG_KEYWORDS = ("내부통제", "관리조치", "수립", "운영", "이행")


def _txt(cell: RawCell) -> str:
    return cell.text.strip() if cell else ""


def _norm(s: str) -> str:
    return s.replace("\u00a0", " ").strip()


# ---------------------------------------------------------------------------
# 그룹화
# ---------------------------------------------------------------------------
def _group_executives(tables: list[RawTable]) -> list[dict]:
    """
    (EXEC_INFO, RESP, OBLIGATION) 3표 = 1 임원. EXEC_INFO를 경계로 그룹화.
    """
    groups: list[dict] = []
    current: dict | None = None
    for t in tables:
        if t.table_type == "EXEC_INFO":
            if current is not None:
                groups.append(current)
            current = {"exec_info": t}
        elif current is not None:
            if t.table_type == "RESP" and "resp" not in current:
                current["resp"] = t
            elif t.table_type == "OBLIGATION" and "obligation" not in current:
                current["obligation"] = t
    if current is not None:
        groups.append(current)
    return groups


# ---------------------------------------------------------------------------
# 표A (EXEC_INFO)
# ---------------------------------------------------------------------------
def _parse_exec_info(table: RawTable) -> tuple[dict, list[Committee]]:
    """
    라벨 기반으로 값 추출. 셀을 좌→우로 훑으며 라벨 매칭 시 다음 셀을 값으로.
    """
    fields: dict[str, str] = {
        "position": "",
        "name": "",
        "title": "",
        "appointed_date": "",
        "concurrent_yn": "",
        "concurrent_detail": "",
        "departments": "",
    }
    committees: list[Committee] = []

    for row in table.rows:
        cells = row.cells
        i = 0
        while i < len(cells):
            label = _norm(cells[i].text)
            next_cell = cells[i + 1] if i + 1 < len(cells) else None

            if LABEL_POSITION.match(label) and next_cell:
                fields["position"] = _txt(next_cell)
            elif LABEL_NAME.match(label) and next_cell:
                fields["name"] = _txt(next_cell)
            elif LABEL_TITLE.match(label) and next_cell:
                fields["title"] = _txt(next_cell)
            elif LABEL_APPT_DATE.match(label) and next_cell:
                fields["appointed_date"] = _txt(next_cell)
            elif LABEL_CONCUR_YN.match(label) and not LABEL_CONCUR_DTL.match(label) and next_cell:
                fields["concurrent_yn"] = _txt(next_cell)
            elif LABEL_CONCUR_DTL.match(label) and next_cell:
                fields["concurrent_detail"] = _txt(next_cell)
            elif LABEL_DEPT.match(label) and next_cell:
                fields["departments"] = _txt(next_cell)
            elif LABEL_COMMITTEE_ROOT.match(label) and next_cell:
                committees = _parse_committee_nested(next_cell)
            else:
                # label 아니면 넘어감 (값 셀은 자연스럽게 skip)
                pass
            i += 1

    # 2-pass: '현 직책 부여일'은 멀티라인 라벨이라 _norm 결과가 '현 직책 부여일\n(임원 선임일 등)'.
    # match가 실패할 수 있으므로 label 시작이 '현' 인 경우 startswith fallback.
    if not fields["appointed_date"]:
        for row in table.rows:
            for i, cell in enumerate(row.cells[:-1]):
                label = _norm(cell.text).split("\n", 1)[0]
                if LABEL_APPT_DATE.match(label):
                    fields["appointed_date"] = _txt(row.cells[i + 1])
                    break

    return fields, committees


def _parse_committee_nested(cell: RawCell) -> list[Committee]:
    if not cell.nested_tables:
        return []
    nested = cell.nested_tables[0]
    if len(nested.rows) < 2:
        return []
    # Row 0 = 헤더, Row 1~ = 데이터
    result: list[Committee] = []
    for row in nested.rows[1:]:
        cells = row.cells
        if len(cells) < 1:
            continue
        name = _txt(cells[0]) if len(cells) > 0 else ""
        if not name:
            continue
        role = _txt(cells[1]) if len(cells) > 1 else ""
        cycle = _txt(cells[2]) if len(cells) > 2 else ""
        matters = _txt(cells[3]) if len(cells) > 3 else ""
        result.append(Committee(name=name, role=role, cycle=cycle, matters=matters))
    return result


# ---------------------------------------------------------------------------
# 표B (RESP)
# ---------------------------------------------------------------------------
def _parse_resp(table: RawTable, table_index: int) -> tuple[str, str, list[Responsibility]]:
    """
    개요/배분일자 + 책무 데이터 추출. 섹션 라벨로 경계 인식.
    """
    summary = ""
    assign_date = ""
    responsibilities: list[Responsibility] = []

    rows = table.rows
    i = 0
    while i < len(rows):
        cells = rows[i].cells
        labels = [_norm(c.text) for c in cells]

        # '책무 개요' 헤더 → 다음 행이 summary+date
        if any(LABEL_RESP_SUMMARY.match(t) for t in labels) or any(
            LABEL_ASSIGN_DATE.match(t) for t in labels
        ):
            if i + 1 < len(rows):
                data_cells = rows[i + 1].cells
                if len(data_cells) >= 1:
                    summary = data_cells[0].text.strip()
                if len(data_cells) >= 2:
                    assign_date = data_cells[-1].text.strip()
            i += 2
            continue

        # 책무 데이터 헤더: 첫 셀 = "책무" + 다른 셀에 "세부/법령/내규"
        if (
            labels
            and PATTERN_RESP_HEADER.match(labels[0])
            and any(PATTERN_RESP_DETAIL_COLS.search(t) for t in labels)
        ):
            for data_idx, data_row in enumerate(rows[i + 1:], start=i + 1):
                dc = data_row.cells
                if not dc:
                    continue
                category = _txt(dc[0])
                if not category:
                    continue
                detail_text = _txt(dc[1]) if len(dc) > 1 else ""
                law_reg = _txt(dc[2]) if len(dc) > 2 else ""
                law_reg_clean = _strip_trailing_deung(law_reg)
                responsibilities.append(
                    Responsibility(
                        category=category,
                        details=[detail_text] if detail_text else [],
                        laws=[],
                        regulations=[],
                        raw_law_reg=law_reg_clean,
                        source=SourceRef(table=table_index, row=data_idx, cols=[0, 1, 2]),
                    )
                )
            break

        i += 1

    return summary, assign_date, responsibilities


def _strip_trailing_deung(text: str) -> str:
    """
    나열 말미의 단독 '등' 제거. 예: '... 개인정보보호법, 예금자보호법 등' → '... 개인정보보호법, 예금자보호법'.
    단, '등에 관한 법률' 같이 의미 있는 '등'은 유지.
    """
    if not text:
        return text
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # 줄 말미 ' 등' 제거 (단어 '등에' 등은 유지)
        stripped = re.sub(r"(?<=[가-힣a-zA-Z0-9)])(\s+등)\s*$", "", line)
        cleaned.append(stripped)
    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# 표C (OBLIGATION)
# ---------------------------------------------------------------------------
def _parse_obligation(
    table: RawTable, position: str, table_index: int
) -> list[Obligation]:
    if not table.rows or not table.rows[0].cells:
        return []
    cell = table.rows[0].cells[0]
    if not cell.paragraphs:
        return []

    blocks: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_items: list[str] = []
    for p in cell.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if p.is_bold:
            if current_title is not None:
                blocks.append((current_title, current_items))
            current_title = text
            current_items = []
        else:
            if current_title is None:
                # bold 제목 나오기 전 선행 텍스트 — 버퍼링
                current_title = ""
            current_items.append(text)
    if current_title is not None:
        blocks.append((current_title, current_items))

    is_ceo = bool(_CEO_PATTERN.search(position))
    result: list[Obligation] = []
    for idx, (title, items) in enumerate(blocks):
        obl_type: ObligationType = _resolve_obligation_type(
            idx, len(blocks), title, is_ceo
        )
        result.append(
            Obligation(
                type=obl_type,
                category=title,
                items=items,
                source=SourceRef(table=table_index, row=0, cols=[0]),
            )
        )
    return result


def _resolve_obligation_type(
    idx: int, total: int, title: str, is_ceo: bool
) -> ObligationType:
    if is_ceo:
        return "고유 책무"
    if idx == total - 1 and _is_common_obligation_title(title):
        return "공통 책무"
    return "고유 책무"


def _is_common_obligation_title(title: str) -> bool:
    """마지막 블록이 공통책무인지 키워드 기반 판정."""
    return sum(1 for kw in _COMMON_OBLIG_KEYWORDS if kw in title) >= 3


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
def normalize(raw: RawDocument) -> ParsedDocument:
    """RawDocument → ParsedDocument."""
    classify_all(raw.tables)
    groups = _group_executives(raw.tables)

    executives: list[Executive] = []
    for idx, g in enumerate(groups):
        exec_info_table: RawTable = g["exec_info"]
        resp_table: RawTable | None = g.get("resp")
        obligation_table: RawTable | None = g.get("obligation")

        fields, committees = _parse_exec_info(exec_info_table)
        summary, assign_date, responsibilities = (
            _parse_resp(resp_table, resp_table.source_index)
            if resp_table
            else ("", "", [])
        )
        obligations = (
            _parse_obligation(
                obligation_table, fields["position"], obligation_table.source_index
            )
            if obligation_table
            else []
        )

        executives.append(
            Executive(
                id=f"exec_{idx + 1:02d}",
                position=fields["position"],
                name=fields["name"],
                title=fields["title"],
                appointed_date=fields["appointed_date"],
                concurrent_yn=fields["concurrent_yn"],
                concurrent_detail=fields["concurrent_detail"],
                departments=fields["departments"],
                committees=committees,
                responsibility_summary=summary,
                assign_date=assign_date,
                responsibilities=responsibilities,
                obligations=obligations,
                footnotes=Footnotes(),
            )
        )

    parse_info = ParseInfo(
        file_name=Path(raw.source_path).name,
        total_pages=0,
        executive_count=len(executives),
        parse_date=datetime.now().strftime("%Y-%m-%d"),
    )
    return ParsedDocument(executives=executives, parse_info=parse_info)
