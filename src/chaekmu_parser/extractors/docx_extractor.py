"""
DOCX extractor — python-docx 기반.

규칙:
  - 모든 top-level 테이블 순서대로 추출
  - 각 셀: paragraphs(텍스트+bold 플래그) + 중첩 테이블 보존
  - Merged cell dedup: 같은 <w:tc> 엘리먼트가 여러 번 노출되는 경우 1회만 유지
  - text/is_bold는 단락 결합 결과로 채움 (하위 호환)
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.table import Table as DocxTable
from docx.table import _Cell as DocxCell

from chaekmu_parser.extractors.base import BaseExtractor
from chaekmu_parser.models import (
    RawCell,
    RawDocument,
    RawParagraph,
    RawRow,
    RawTable,
)


class DocxExtractor(BaseExtractor):

    @property
    def format_name(self) -> str:
        return "docx"

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".docx"

    def extract(self, file_path: Path) -> RawDocument:
        doc = Document(str(file_path))

        tables = [
            self._convert_table(t, source_index=idx)
            for idx, t in enumerate(doc.tables)
        ]

        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

        return RawDocument(
            source_path=str(file_path),
            format="docx",
            tables=tables,
            paragraphs=paragraphs,
        )

    def _convert_table(self, table: DocxTable, source_index: int) -> RawTable:
        rows: list[RawRow] = []
        for row in table.rows:
            seen_tc: set[int] = set()
            cells: list[RawCell] = []
            for cell in row.cells:
                tc_id = id(cell._tc)
                if tc_id in seen_tc:
                    continue
                seen_tc.add(tc_id)
                cells.append(self._convert_cell(cell))
            rows.append(RawRow(cells=cells))
        return RawTable(rows=rows, source_index=source_index)

    def _convert_cell(self, cell: DocxCell) -> RawCell:
        paragraphs: list[RawParagraph] = []
        for p in cell.paragraphs:
            text = p.text
            is_bold = any(run.bold is True for run in p.runs)
            paragraphs.append(RawParagraph(text=text, is_bold=is_bold))

        joined_text = "\n".join(p.text for p in paragraphs)
        any_bold = any(p.is_bold and p.text.strip() for p in paragraphs)

        nested_tables: list[RawTable] = [
            self._convert_table(nt, source_index=-1)
            for nt in cell.tables
        ]

        return RawCell(
            text=joined_text,
            is_bold=any_bold,
            nested_tables=nested_tables,
            paragraphs=paragraphs,
        )
