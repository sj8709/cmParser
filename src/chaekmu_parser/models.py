"""
통일 데이터 모델.

두 계층으로 분리:
  1. Raw 계층 (RawDocument): extractor 출력. 원본 구조 보존, 가공 금지.
  2. Parsed 계층 (ParsedDocument): normalizer 출력. Java 파서의 JSON 출력과 동일한 구조.

정합성 검증용으로 Parsed 계층의 각 항목은 `raw` 참조 좌표를 함께 보관한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TableType = Literal["EXEC_INFO", "COMMITTEE", "RESP", "OBLIGATION", "UNKNOWN"]
FormatType = Literal["docx", "hwp", "pdf"]
ObligationType = Literal["고유 책무", "공통 책무"]


@dataclass
class RawParagraph:
    text: str
    is_bold: bool = False


@dataclass
class RawCell:
    text: str
    is_bold: bool = False
    nested_tables: list["RawTable"] = field(default_factory=list)
    paragraphs: list[RawParagraph] = field(default_factory=list)


@dataclass
class RawRow:
    cells: list[RawCell]


@dataclass
class RawTable:
    rows: list[RawRow]
    source_index: int
    table_type: TableType = "UNKNOWN"


@dataclass
class RawDocument:
    """Extractor 출력 - 원본 구조 보존."""
    source_path: str
    format: FormatType
    tables: list[RawTable]
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class SourceRef:
    """정합성 검증용 원본 좌표."""
    table: int
    row: int
    cols: list[int] = field(default_factory=list)


@dataclass
class Committee:
    name: str
    role: str
    cycle: str
    matters: str


@dataclass
class Responsibility:
    category: str
    details: list[str]
    laws: list[str]
    regulations: list[str]
    raw_law_reg: str = ""
    source: SourceRef | None = None


@dataclass
class Obligation:
    type: ObligationType
    category: str
    items: list[str]
    source: SourceRef | None = None


@dataclass
class Footnotes:
    executive_info: str = ""
    responsibility: str = ""
    obligation: str = ""


@dataclass
class Executive:
    id: str
    position: str
    name: str
    title: str
    appointed_date: str
    concurrent_yn: str
    concurrent_detail: str
    departments: str
    committees: list[Committee] = field(default_factory=list)
    responsibility_summary: str = ""
    assign_date: str = ""
    responsibilities: list[Responsibility] = field(default_factory=list)
    obligations: list[Obligation] = field(default_factory=list)
    footnotes: Footnotes = field(default_factory=Footnotes)


@dataclass
class ParseInfo:
    file_name: str
    total_pages: int
    executive_count: int
    parse_date: str


@dataclass
class ParsedDocument:
    """Normalizer 출력 - Java 파서 JSON과 동일 구조."""
    executives: list[Executive]
    parse_info: ParseInfo
