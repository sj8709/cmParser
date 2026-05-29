"""검증 리포트 상세 뷰어 — Toplevel 창으로 ValidationReport 표시."""

from __future__ import annotations

import customtkinter as ctk

from chaekmu_parser.validator import ValidationIssue, ValidationReport

_SEVERITY_ICON = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}
_STAGE_TITLE = {
    1: "Stage 1 · 재추출 비교",
    2: "Stage 2 · raw 대조",
    3: "Stage 3 · 재조립 유사도",
    4: "Stage 4 · 구조 정합성",
    5: "Stage 5 · 공통/고유 정합성",
}


class ReportWindow(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, report: ValidationReport) -> None:
        super().__init__(master)
        self.title("검증 리포트")
        self.geometry("720x560")
        self.minsize(600, 400)

        self._build(report)

    def _build(self, report: ValidationReport) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=16)

        # 헤더 요약
        status = "✓ 통과" if report.passed else "❌ 실패"
        color = (
            "#2e7d32" if report.passed and not report.has_warnings
            else "#f9a825" if report.passed and report.has_warnings
            else "#c62828"
        )
        header = ctk.CTkLabel(
            container, text=f"{status}",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=color, anchor="w",
        )
        header.pack(fill="x", pady=(0, 6))

        counts = report.counts_by_severity()
        summary_lines = [
            f"• 오류 {counts['error']} · 경고 {counts['warn']} · 정보 {counts['info']}",
            f"• Stage 1 (재추출 비교) — 원본 단락 {report.stage1_source_fragments}개 중 raw 누락 {report.stage1_missing_fragments}개",
            f"• Stage 2 (parsed → raw 대조) — 확인 {report.stage2_verified_count}건, 누락 {report.stage2_missing_count}건",
            f"• Stage 3 (재조립 유사도) — {report.stage3_similarity:.1%}",
            f"• Stage 4 (구조 정합성) — 오추출 의심 {report.stage4_oversplit_count}건, 원본 누락 추정 {report.stage4_missing_count}건, 책무명 비동일 {report.stage4_nonidentical_count}건",
            f"• Stage 5 (공통/고유 정합성) — 공통 분류 불일치 {report.stage5_common_mismatch_count}건",
        ]
        for line in summary_lines:
            label = ctk.CTkLabel(container, text=line, anchor="w",
                                 font=ctk.CTkFont(size=12))
            label.pack(fill="x", pady=1)

        ctk.CTkLabel(
            container, text="", height=1, fg_color="gray40",
        ).pack(fill="x", pady=(10, 10))

        # 이슈 상세 리스트
        list_label = ctk.CTkLabel(
            container, text=f"상세 항목 ({len(report.issues)}건)",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        )
        list_label.pack(fill="x", pady=(0, 4))

        textbox = ctk.CTkTextbox(
            container, font=ctk.CTkFont(family="Consolas", size=12),
        )
        textbox.pack(fill="both", expand=True)

        if not report.issues:
            textbox.insert("end", "검출된 이슈가 없습니다. 모든 단계 통과.\n")
        else:
            self._render_issues_grouped(textbox, report.issues)

        textbox.configure(state="disabled")

        close_btn = ctk.CTkButton(
            container, text="닫기", width=100, command=self.destroy,
        )
        close_btn.pack(pady=(10, 0))

    @classmethod
    def _render_issues_grouped(cls, textbox, issues: list[ValidationIssue]) -> None:
        """Stage별로 묶어 헤더·구분선과 함께 렌더링 — 단계 경계를 한눈에."""
        index = 0
        for stage in sorted({i.stage for i in issues}):
            stage_issues = [i for i in issues if i.stage == stage]
            title = _STAGE_TITLE.get(stage, f"Stage {stage}")
            textbox.insert("end", f"━━ {title} ({len(stage_issues)}건) " + "━" * 8 + "\n")
            for issue in stage_issues:
                index += 1
                cls._render_issue(textbox, index, issue)
            textbox.insert("end", "\n")

    @staticmethod
    def _render_issue(textbox, index: int, issue: ValidationIssue) -> None:
        icon = _SEVERITY_ICON.get(issue.severity, "•")
        textbox.insert("end", f"  [{index:3d}] {icon} {issue.message}\n")
        if issue.context:
            textbox.insert("end", f"          └ 대상: {issue.context}\n")
