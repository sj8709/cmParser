"""
파이프라인 백그라운드 실행.

UI(메인 스레드) → 워커 스레드: `run_pipeline_async`로 시작.
워커 → UI: `queue.Queue`에 (level, message, payload) 튜플 push.
메인 스레드는 `root.after(100, poll)`로 큐를 polling.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from chaekmu_parser.extractors.docx_extractor import DocxExtractor
from chaekmu_parser.normalizer import normalize
from chaekmu_parser.xlsx_writer import write
from chaekmu_parser_gui.logging_setup import friendly_error, get_logger

Level = Literal["info", "ok", "warn", "error", "done"]


@dataclass(frozen=True)
class StatusMessage:
    level: Level
    text: str
    output_path: Path | None = None


@dataclass(frozen=True)
class PipelineRequest:
    input_path: Path
    output_dir: Path
    template_path: Path


def template_path() -> Path:
    """실행 모드 무관하게 templates/chaekmu_template.xlsx 위치 추적."""
    # 1) PyInstaller 번들: sys._MEIPASS/templates/...
    import sys
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        p = Path(bundled) / "templates" / "chaekmu_template.xlsx"
        if p.exists():
            return p
    # 2) 개발 환경: 프로젝트 루트 templates/
    for parent in Path(__file__).resolve().parents:
        cand = parent / "templates" / "chaekmu_template.xlsx"
        if cand.exists():
            return cand
    raise FileNotFoundError("chaekmu_template.xlsx를 찾을 수 없습니다.")


def output_filename(input_path: Path) -> str:
    """입력 파일 stem 기반 출력 파일명 — <stem>_output_<YYYYMMDD>.xlsx."""
    today = datetime.now().strftime("%Y%m%d")
    return f"{input_path.stem}_output_{today}.xlsx"


def run_pipeline_async(
    request: PipelineRequest, status_queue: "queue.Queue[StatusMessage]"
) -> threading.Thread:
    """워커 스레드를 시작하고 핸들 반환. 메인 스레드는 이를 join 하지 말 것 (UI freeze)."""
    t = threading.Thread(
        target=_run_pipeline, args=(request, status_queue), daemon=True
    )
    t.start()
    return t


# ---------------------------------------------------------------------------
# 워커 본체 — UI 스레드에서 호출 금지
# ---------------------------------------------------------------------------
def _run_pipeline(request: PipelineRequest, q: "queue.Queue[StatusMessage]") -> None:
    log = get_logger()
    log.info("pipeline start: input=%s output_dir=%s", request.input_path, request.output_dir)
    try:
        q.put(StatusMessage("info", f"📄 입력 로딩: {request.input_path.name}"))
        raw = DocxExtractor().extract(request.input_path)
        log.info("extracted %d tables", len(raw.tables))
        q.put(StatusMessage("ok", f"✓ 추출 완료 — 테이블 {len(raw.tables)}개"))

        q.put(StatusMessage("info", "⚙ 정규화 중..."))
        parsed = normalize(raw)
        log.info("normalized %d executives", len(parsed.executives))
        q.put(StatusMessage(
            "ok", f"✓ 정규화 완료 — 임원 {len(parsed.executives)}명"
        ))

        unknown = [t for t in raw.tables if t.table_type == "UNKNOWN"]
        if unknown:
            log.warning("UNKNOWN tables: %d (indices=%s)",
                        len(unknown), [t.source_index for t in unknown])
            q.put(StatusMessage(
                "warn", f"⚠ 분류 실패 {len(unknown)}개 (리뷰 필요)"
            ))

        q.put(StatusMessage("info", "💾 XLSX 작성 중..."))
        out_path = request.output_dir / output_filename(request.input_path)
        write(parsed, request.template_path, out_path)
        log.info("wrote %s", out_path)
        q.put(StatusMessage(
            "done", f"✓ 저장 완료: {out_path.name}", output_path=out_path
        ))
    except Exception as e:
        log.exception("pipeline failed")
        q.put(StatusMessage("error", friendly_error(e)))
