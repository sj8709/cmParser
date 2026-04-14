"""
3단계 정합성 검증 레이어 (HANDOFF §5.4).

1. **Stage 1 (재추출 비교)**: RawDocument가 원본을 충실히 담았는지 — 독립 경로로
   원본을 한 번 더 훑어 얻은 텍스트 세트와 raw 셀 텍스트를 비교.
2. **Stage 2 (parsed → raw substring)**: ParsedDocument의 각 verbatim 필드가
   raw 셀 텍스트 어딘가에 실제로 존재하는지 점검. 누락 = 후처리 왜곡 또는 파싱 오류.
3. **Stage 3 (역재조립 유사도)**: parsed 전체를 문자열로 재조립 후 raw와 유사도 측정.
   낮으면 대규모 누락/중복 가능성.

결과는 `ValidationReport`로 반환. GUI/테스트가 소비.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from chaekmu_parser.models import (
    Executive,
    ParsedDocument,
    RawDocument,
    RawTable,
)

Severity = Literal["info", "warn", "error"]
Stage = Literal[1, 2, 3]

# ---------------------------------------------------------------------------
# 결과 자료구조
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ValidationIssue:
    stage: Stage
    severity: Severity
    message: str
    context: str = ""  # 임원 직책, 필드명 등


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    # Stage 1
    stage1_source_fragments: int = 0
    stage1_missing_fragments: int = 0

    # Stage 2
    stage2_verified_count: int = 0
    stage2_missing_count: int = 0

    # Stage 3
    stage3_similarity: float = 0.0

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warn" for i in self.issues)

    def counts_by_severity(self) -> dict[Severity, int]:
        result: dict[Severity, int] = {"info": 0, "warn": 0, "error": 0}
        for i in self.issues:
            result[i.severity] += 1
        return result

    def summary_line(self) -> str:
        c = self.counts_by_severity()
        status = "✓ 통과" if self.passed else "❌ 실패"
        return (
            f"{status} — 오류 {c['error']} · 경고 {c['warn']} · 정보 {c['info']} | "
            f"Stage1 누락 {self.stage1_missing_fragments}/"
            f"{self.stage1_source_fragments} · "
            f"Stage2 확인 {self.stage2_verified_count} (누락 {self.stage2_missing_count}) · "
            f"Stage3 유사도 {self.stage3_similarity:.1%}"
        )


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
# Stage별 임계치 — 본 임계치 이하로 떨어지면 경고/오류
_STAGE1_MISSING_RATIO_WARN = 0.01   # 1% 이상 누락
_STAGE1_MISSING_RATIO_ERROR = 0.05  # 5% 이상 누락 → 오류
_STAGE3_SIMILARITY_WARN = 0.55
_STAGE3_SIMILARITY_ERROR = 0.30
_MAX_MISSING_ISSUE_PER_STAGE = 10


def validate(
    parsed: ParsedDocument, raw: RawDocument, source_path: Path | None = None
) -> ValidationReport:
    """3단계 검증 실행."""
    report = ValidationReport()
    _run_stage1(parsed, raw, source_path, report)
    _run_stage2(parsed, raw, report)
    _run_stage3(parsed, raw, report)
    return report


# ---------------------------------------------------------------------------
# Stage 1
# ---------------------------------------------------------------------------
def _run_stage1(
    parsed: ParsedDocument,
    raw: RawDocument,
    source_path: Path | None,
    report: ValidationReport,
) -> None:
    source_fragments = _extract_source_fragments(source_path, raw.format)
    if source_fragments is None:
        # 지원하지 않는 포맷은 Stage 1 생략 (예: Phase 2 HWP 전)
        return
    raw_joined = _raw_text_blob(raw)
    missing: list[str] = [f for f in source_fragments if f not in raw_joined]
    report.stage1_source_fragments = len(source_fragments)
    report.stage1_missing_fragments = len(missing)

    if not source_fragments:
        return
    ratio = len(missing) / len(source_fragments)
    if ratio >= _STAGE1_MISSING_RATIO_ERROR:
        report.issues.append(ValidationIssue(
            1, "error",
            f"Stage 1 — 원본의 {ratio:.1%} 단락이 raw에 없음. Extractor 오류 가능성 높음"
        ))
    elif ratio >= _STAGE1_MISSING_RATIO_WARN:
        report.issues.append(ValidationIssue(
            1, "warn",
            f"Stage 1 — 원본의 {ratio:.1%} 단락이 raw에 없음"
        ))
    for m in missing[:_MAX_MISSING_ISSUE_PER_STAGE]:
        report.issues.append(ValidationIssue(
            1, "warn", f"Stage 1 — 누락 단락: {_truncate(m, 80)}"
        ))


def _extract_source_fragments(
    source_path: Path | None, fmt: str
) -> list[str] | None:
    """원본을 독립 경로로 훑어 non-empty stripped 단락 리스트 반환. 지원 안하면 None."""
    if source_path is None or not source_path.exists():
        return None
    if fmt == "docx":
        return _docx_fragments(source_path)
    # hwp/pdf는 Phase 2/3에서 확장
    return None


def _docx_fragments(path: Path) -> list[str]:
    """python-docx로 모든 단락·테이블·중첩테이블을 한 번 더 훑는다 (DocxExtractor와 독립)."""
    from docx import Document
    from docx.table import Table as DocxTable

    doc = Document(str(path))
    fragments: list[str] = []

    def walk_cell(cell) -> None:
        for p in cell.paragraphs:
            txt = p.text.strip()
            if txt:
                fragments.append(txt)
        for t in cell.tables:
            walk_table(t)

    def walk_table(t: DocxTable) -> None:
        seen: set[int] = set()
        for row in t.rows:
            for cell in row.cells:
                tc_id = id(cell._tc)
                if tc_id in seen:
                    continue
                seen.add(tc_id)
                walk_cell(cell)

    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            fragments.append(t)
    for table in doc.tables:
        walk_table(table)
    return fragments


def _raw_text_blob(raw: RawDocument) -> str:
    """RawDocument의 모든 셀 텍스트와 top-level 단락을 하나의 문자열로."""
    parts: list[str] = list(raw.paragraphs)
    for t in raw.tables:
        parts.extend(_collect_cell_text(t))
    return "\n".join(parts)


def _collect_cell_text(t: RawTable) -> list[str]:
    out: list[str] = []
    for row in t.rows:
        for cell in row.cells:
            if cell.text:
                out.append(cell.text)
            for nested in cell.nested_tables:
                out.extend(_collect_cell_text(nested))
    return out


# ---------------------------------------------------------------------------
# Stage 2
# ---------------------------------------------------------------------------
def _run_stage2(
    parsed: ParsedDocument, raw: RawDocument, report: ValidationReport
) -> None:
    """각 임원의 verbatim 필드가 raw에 실제로 존재하는지 확인."""
    raw_blob = _raw_text_blob(raw)
    verified = 0
    missing_details: list[tuple[str, str, str]] = []  # (exec, field, value)

    for e in parsed.executives:
        for field_name, value in _verbatim_fields(e):
            if not value:
                continue
            if value in raw_blob:
                verified += 1
            else:
                missing_details.append((e.position.replace("\n", ", "), field_name, value))

    report.stage2_verified_count = verified
    report.stage2_missing_count = len(missing_details)

    if not missing_details:
        return

    report.issues.append(ValidationIssue(
        2, "warn",
        f"Stage 2 — raw에서 찾을 수 없는 parsed 값 {len(missing_details)}건"
    ))
    for pos, fname, val in missing_details[:_MAX_MISSING_ISSUE_PER_STAGE]:
        report.issues.append(ValidationIssue(
            2, "warn",
            f"Stage 2 — {fname} = {_truncate(val, 60)}",
            context=pos,
        ))


def _verbatim_fields(e: Executive) -> list[tuple[str, str]]:
    """원본과 글자 단위로 동일해야 하는 필드 목록.

    라벨 매칭 위해 trimming은 했지만 법령 '등' 제거 같은 후처리된 필드는 제외.
    """
    fields: list[tuple[str, str]] = [
        ("name", e.name),
        ("title", e.title),
        ("appointed_date", e.appointed_date),
        ("concurrent_yn", e.concurrent_yn),
        ("departments", e.departments),
    ]
    for idx, c in enumerate(e.committees):
        fields.append((f"committee[{idx}].name", c.name))
        fields.append((f"committee[{idx}].role", c.role))
    for idx, r in enumerate(e.responsibilities):
        fields.append((f"responsibility[{idx}].category", r.category))
        if r.details:
            fields.append((f"responsibility[{idx}].details", r.details[0]))
    for idx, o in enumerate(e.obligations):
        fields.append((f"obligation[{idx}].category", o.category))
        for i, item in enumerate(o.items):
            fields.append((f"obligation[{idx}].items[{i}]", item))
    return fields


# ---------------------------------------------------------------------------
# Stage 3
# ---------------------------------------------------------------------------
def _run_stage3(
    parsed: ParsedDocument, raw: RawDocument, report: ValidationReport
) -> None:
    raw_blob = _raw_text_blob(raw)
    parsed_blob = _parsed_text_blob(parsed)
    # quick_ratio는 set-based 빠른 근사. 정확한 ratio는 O(n²)이라 대용량 부적합.
    matcher = SequenceMatcher(None, raw_blob, parsed_blob, autojunk=True)
    sim = matcher.quick_ratio()
    report.stage3_similarity = sim

    if sim < _STAGE3_SIMILARITY_ERROR:
        report.issues.append(ValidationIssue(
            3, "error",
            f"Stage 3 — 재조립 유사도 {sim:.1%} — 대규모 누락/중복 의심"
        ))
    elif sim < _STAGE3_SIMILARITY_WARN:
        report.issues.append(ValidationIssue(
            3, "warn",
            f"Stage 3 — 재조립 유사도 {sim:.1%} — 검토 권장"
        ))


def _parsed_text_blob(parsed: ParsedDocument) -> str:
    parts: list[str] = []
    for e in parsed.executives:
        parts.extend([e.position, e.name, e.title, e.appointed_date])
        parts.append(e.concurrent_detail)
        parts.append(e.departments)
        for c in e.committees:
            parts.extend([c.name, c.role, c.cycle, c.matters])
        parts.append(e.responsibility_summary)
        parts.append(e.assign_date)
        for r in e.responsibilities:
            parts.append(r.category)
            parts.extend(r.details)
            parts.append(r.raw_law_reg)
        for o in e.obligations:
            parts.extend([o.category, *o.items])
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------
def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"
