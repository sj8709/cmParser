"""
MainWindow — 책무기술서 파서 GUI 메인 창.

레이아웃은 claudedocs/gui_packaging_design.md §3 참조.
워커 연동·로깅은 #13/#14에서 덧붙임.
"""

from __future__ import annotations

import os
import queue
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from chaekmu_parser.validator import ValidationReport
from chaekmu_parser_gui.logging_setup import current_log_file, setup_logging
from chaekmu_parser_gui.report_window import ReportWindow
from chaekmu_parser_gui.workers import (
    PipelineRequest,
    StatusMessage,
    run_pipeline_async,
    template_path,
)

APP_TITLE = "책무기술서 파서"
APP_VERSION = "0.1.0"
WINDOW_SIZE = "680x620"

DEFAULT_OUTPUT_DIR = Path.home() / "Desktop"


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        setup_logging()
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry(WINDOW_SIZE)
        self.minsize(600, 560)

        self._input_path = ctk.StringVar(value="")
        self._output_dir = ctk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self._status_queue: queue.Queue[StatusMessage] = queue.Queue()
        self._last_output: Path | None = None
        self._last_report: ValidationReport | None = None
        self._running = False

        self._build_layout()

    # -----------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------
    def _build_layout(self) -> None:
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=20, pady=16)

        self._build_header(root)
        self._build_input_row(root)
        self._build_output_row(root)
        self._build_action_row(root)
        self._build_progress(root)
        self._build_log(root)
        self._build_footer(root)

    def _build_header(self, parent) -> None:
        header = ctk.CTkLabel(
            parent,
            text="📋 책무기술서 파서",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        )
        header.pack(fill="x", pady=(0, 4))
        subtitle = ctk.CTkLabel(
            parent,
            text="DOCX 책무기술서를 XLSX 템플릿으로 변환합니다.",
            font=ctk.CTkFont(size=12),
            text_color="gray60",
            anchor="w",
        )
        subtitle.pack(fill="x", pady=(0, 16))

    def _build_input_row(self, parent) -> None:
        label = ctk.CTkLabel(parent, text="📄 입력 DOCX", anchor="w")
        label.pack(fill="x", pady=(0, 4))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        entry = ctk.CTkEntry(row, textvariable=self._input_path, placeholder_text="DOCX 파일을 선택하세요")
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn = ctk.CTkButton(row, text="찾아보기...", width=110, command=self._on_pick_input)
        btn.pack(side="right")

    def _build_output_row(self, parent) -> None:
        label = ctk.CTkLabel(parent, text="💾 저장 위치", anchor="w")
        label.pack(fill="x", pady=(0, 4))
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 16))
        entry = ctk.CTkEntry(row, textvariable=self._output_dir)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn = ctk.CTkButton(row, text="변경...", width=110, command=self._on_pick_output)
        btn.pack(side="right")

    def _build_action_row(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        self._run_btn = ctk.CTkButton(
            row,
            text="▶   변환 실행",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            command=self._on_run,
        )
        self._run_btn.pack(fill="x")

    def _build_progress(self, parent) -> None:
        self._progress = ctk.CTkProgressBar(parent, mode="indeterminate", height=8)
        self._progress.pack(fill="x", pady=(0, 12))
        self._progress.set(0)

    def _build_log(self, parent) -> None:
        label = ctk.CTkLabel(parent, text="진행 상황", anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
        label.pack(fill="x", pady=(0, 4))
        self._log = ctk.CTkTextbox(parent, height=180, font=ctk.CTkFont(family="Consolas", size=12))
        self._log.pack(fill="both", expand=True, pady=(0, 12))
        self._log.insert("end", "대기 중...\n")
        self._log.configure(state="disabled")

    def _build_footer(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x")
        self._open_folder_btn = ctk.CTkButton(
            row, text="📂 결과 폴더", width=130, state="disabled",
            command=self._on_open_folder,
        )
        self._open_folder_btn.pack(side="left")
        self._report_btn = ctk.CTkButton(
            row, text="🔍 검증 리포트", width=140, state="disabled",
            command=self._on_open_report,
        )
        self._report_btn.pack(side="left", padx=(8, 0))
        log_btn = ctk.CTkButton(
            row, text="📝 로그 파일", width=130, fg_color="gray50", hover_color="gray40",
            command=self._on_open_log,
        )
        log_btn.pack(side="left", padx=(8, 0))
        reset_btn = ctk.CTkButton(
            row, text="초기화", width=100, fg_color="gray50", hover_color="gray40",
            command=self._on_reset,
        )
        reset_btn.pack(side="right")

    # -----------------------------------------------------------------
    # Event handlers (파이프라인 연동은 #13에서)
    # -----------------------------------------------------------------
    def _on_pick_input(self) -> None:
        path = filedialog.askopenfilename(
            title="DOCX 파일 선택",
            filetypes=[("Word 문서", "*.docx"), ("모든 파일", "*.*")],
            initialdir=str(Path.home()),
        )
        if path:
            self._input_path.set(path)
            self._log_line(f"입력 선택: {Path(path).name}")

    def _on_pick_output(self) -> None:
        path = filedialog.askdirectory(
            title="저장 위치 선택",
            initialdir=self._output_dir.get() or str(Path.home()),
        )
        if path:
            self._output_dir.set(path)

    def _on_run(self) -> None:
        if not self._validate_inputs() or self._running:
            return
        try:
            tpl = template_path()
        except FileNotFoundError as e:
            self._log_line(f"❌ {e}")
            return

        self._clear_log()
        self._log_line("▶ 변환 시작")
        self._set_running(True)
        self._last_output = None

        request = PipelineRequest(
            input_path=Path(self._input_path.get()).resolve(),
            output_dir=Path(self._output_dir.get()).resolve(),
            template_path=tpl,
        )
        run_pipeline_async(request, self._status_queue)
        self.after(100, self._poll_status_queue)

    def _poll_status_queue(self) -> None:
        """워커 → UI 큐 폴링. 100ms 주기로 메시지 소진 후 재등록."""
        try:
            while True:
                msg = self._status_queue.get_nowait()
                self._log_line(msg.text)
                if msg.level == "done":
                    self._last_output = msg.output_path
                    self._last_report = msg.validation_report
                    self._open_folder_btn.configure(state="normal")
                    if msg.validation_report is not None:
                        self._report_btn.configure(state="normal")
                    self._set_running(False)
                    return
                if msg.level == "error":
                    self._set_running(False)
                    return
        except queue.Empty:
            pass

        if self._running:
            self.after(100, self._poll_status_queue)

    def _set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self._run_btn.configure(state="disabled", text="⏳   변환 중...")
            self._progress.start()
        else:
            self._run_btn.configure(state="normal", text="▶   변환 실행")
            self._progress.stop()
            self._progress.set(0)

    def _on_open_folder(self) -> None:
        target = self._last_output.parent if self._last_output else Path(self._output_dir.get())
        if target.exists():
            os.startfile(str(target))  # noqa: S606 (Windows 전용)

    def _on_open_log(self) -> None:
        log_path = current_log_file()
        if not log_path.exists():
            os.startfile(str(log_path.parent))
            return
        os.startfile(str(log_path))

    def _on_open_report(self) -> None:
        if self._last_report is None:
            return
        win = ReportWindow(self, self._last_report)
        win.after(50, win.focus_force)

    def _on_reset(self) -> None:
        if self._running:
            self._log_line("⚠ 변환 중에는 초기화할 수 없습니다.")
            return
        self._input_path.set("")
        self._output_dir.set(str(DEFAULT_OUTPUT_DIR))
        self._open_folder_btn.configure(state="disabled")
        self._last_output = None
        self._clear_log()
        self._log_line("대기 중...")

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    def _validate_inputs(self) -> bool:
        input_p = self._input_path.get().strip()
        output_p = self._output_dir.get().strip()
        if not input_p:
            self._log_line("⚠ 입력 DOCX 파일을 선택해 주세요.")
            return False
        if not Path(input_p).is_file():
            self._log_line(f"⚠ 입력 파일을 찾을 수 없음: {input_p}")
            return False
        if not output_p or not Path(output_p).is_dir():
            self._log_line("⚠ 저장 폴더가 존재하지 않습니다.")
            return False
        return True

    def _log_line(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
