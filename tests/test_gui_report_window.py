"""ReportWindow smoke — headless 생성 후 주요 위젯 존재 확인."""

import customtkinter as ctk

from chaekmu_parser.validator import ValidationIssue, ValidationReport
from chaekmu_parser_gui.report_window import ReportWindow


def _sample_report() -> ValidationReport:
    return ValidationReport(
        issues=[
            ValidationIssue(1, "warn", "샘플 경고", context="대표이사"),
            ValidationIssue(2, "error", "샘플 오류", context="마케팅본부장"),
        ],
        stage1_source_fragments=100,
        stage1_missing_fragments=1,
        stage2_verified_count=60,
        stage2_missing_count=2,
        stage3_similarity=0.72,
    )


def test_report_window_builds_without_error():
    root = ctk.CTk()
    try:
        win = ReportWindow(root, _sample_report())
        win.update()  # 렌더 강제
        assert win.winfo_width() > 0
        win.destroy()
    finally:
        root.destroy()


def test_report_window_handles_empty_issues():
    root = ctk.CTk()
    try:
        empty = ValidationReport()
        win = ReportWindow(root, empty)
        win.update()
        win.destroy()
    finally:
        root.destroy()
