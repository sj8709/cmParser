"""
라벨 기반 테이블 유형 분류.

규칙 출처: 라벨분류_정규식_명세_v0.1.md

핵심 원칙:
  - 테이블 인덱스 의존 X
  - 금융위 시행령 별표1이 강제하는 라벨만 사용
  - UNKNOWN 발생 시 예외 없이 플래그 -> 리뷰 큐
"""

from __future__ import annotations

import re

from chaekmu_parser.models import RawTable, TableType

# ---------------------------------------------------------------------------
# 필드 라벨 정규식
# ---------------------------------------------------------------------------
LABEL_POSITION      = re.compile(r"^\s*직\s*책\s*$")
LABEL_NAME          = re.compile(r"^\s*성\s*명\s*$")
LABEL_TITLE         = re.compile(r"^\s*직\s*위\s*$")
LABEL_APPT_DATE     = re.compile(r"^\s*현\s*직\s*책\s*부\s*여\s*일\s*$")
LABEL_CONCUR_YN     = re.compile(r"^\s*겸\s*직\s*(?:여\s*부)?\s*$")
LABEL_CONCUR_DTL    = re.compile(r"^\s*겸\s*직\s*사\s*항\s*$")
LABEL_DEPT          = re.compile(r"^\s*소\s*관\s*부\s*서\s*$")
LABEL_COMMITTEE_ROOT = re.compile(r"^\s*주\s*관\s*회\s*의\s*체\s*$")
LABEL_ASSIGN_DATE   = re.compile(r"^\s*책\s*무\s*배\s*분\s*일\s*자\s*$")
LABEL_RESP_SUMMARY  = re.compile(r"^\s*책\s*무\s*개\s*요\s*$")

# ---------------------------------------------------------------------------
# 테이블 유형 판정 보조 패턴
# ---------------------------------------------------------------------------
PATTERN_COMMITTEE_NAME    = re.compile(r"회\s*의\s*체\s*명?")
PATTERN_COMMITTEE_ROLE    = re.compile(r"위\s*원\s*장|개\s*최|심\s*의|의\s*결")
PATTERN_RESP_HEADER       = re.compile(r"^\s*책\s*무\s*$")
PATTERN_RESP_DETAIL_COLS  = re.compile(r"세\s*부|법\s*령|내\s*규")
PATTERN_OBLIGATION_TAG    = re.compile(r"<\s*(?:고유|공통)\s*책무\s*>")
PATTERN_OBLIGATION_NUMBER = re.compile(r"[\u2460-\u2473]")  # ①~⑳


def _norm(text: str) -> str:
    """셀 텍스트 정규화 - 분류 매칭용."""
    return text.replace("\u00a0", " ").strip()


def classify_table(table: RawTable) -> TableType:
    """
    테이블 첫 행/셀을 검사하여 유형 판정.

    Returns:
        "EXEC_INFO" | "COMMITTEE" | "RESP" | "OBLIGATION" | "UNKNOWN"
    """
    if not table.rows:
        return "UNKNOWN"

    first_row = table.rows[0]
    if not first_row.cells:
        return "UNKNOWN"

    first_cell = _norm(first_row.cells[0].text)
    header_texts = [_norm(c.text) for c in first_row.cells]

    # 1. EXEC_INFO: 첫 셀이 "직책"
    if LABEL_POSITION.match(first_cell):
        return "EXEC_INFO"

    # 2. COMMITTEE: 헤더에 회의체명 + 위원장/개최/심의/의결
    if any(PATTERN_COMMITTEE_NAME.search(t) for t in header_texts):
        if any(PATTERN_COMMITTEE_ROLE.search(t) for t in header_texts):
            return "COMMITTEE"

    # 3. RESP: "책무 개요" 라벨 포함 OR 책무+세부/법령/내규 헤더 조합
    if any(LABEL_RESP_SUMMARY.match(t) for t in header_texts):
        return "RESP"
    if any(LABEL_ASSIGN_DATE.match(t) for t in header_texts):
        return "RESP"
    if PATTERN_RESP_HEADER.match(first_cell) and any(
        PATTERN_RESP_DETAIL_COLS.search(t) for t in header_texts
    ):
        return "RESP"

    # 4. OBLIGATION: 1행 1열 텍스트 블록
    if len(table.rows) == 1 and len(first_row.cells) == 1:
        body = first_row.cells[0].text
        if PATTERN_OBLIGATION_TAG.search(body):
            return "OBLIGATION"
        if PATTERN_OBLIGATION_NUMBER.search(body):
            return "OBLIGATION"
        # IBK 스타일: bold 단락 존재 (extractor가 is_bold 플래그 세팅 전제)
        if first_row.cells[0].is_bold:
            return "OBLIGATION"

    return "UNKNOWN"


def classify_all(tables: list[RawTable]) -> list[RawTable]:
    """리스트 내 모든 테이블에 table_type 세팅 후 반환 (in-place)."""
    for t in tables:
        t.table_type = classify_table(t)
    return tables
