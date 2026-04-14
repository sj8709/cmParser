"""GUI 워커 E2E — 실 IBK fixture로 파이프라인이 큐를 통해 완료 메시지까지 내보내는지 확인."""

import queue
import time
from pathlib import Path

import pytest

from chaekmu_parser_gui.workers import (
    PipelineRequest,
    output_filename,
    run_pipeline_async,
    template_path,
)

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "fixtures/ibk/input.docx"
pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(), reason="IBK fixture not present"
)


def test_worker_produces_done_message_with_output_path(tmp_path):
    q: queue.Queue = queue.Queue()
    req = PipelineRequest(
        input_path=FIXTURE,
        output_dir=tmp_path,
        template_path=template_path(),
    )
    t = run_pipeline_async(req, q)
    t.join(timeout=60)
    assert not t.is_alive(), "워커가 60초 내에 종료되지 않음"

    messages = []
    while not q.empty():
        messages.append(q.get_nowait())

    levels = [m.level for m in messages]
    assert levels[-1] == "done", f"마지막 메시지가 'done'이 아님: {levels}"
    assert "ok" in levels
    assert "info" in levels

    done_msg = messages[-1]
    assert done_msg.output_path is not None
    assert done_msg.output_path.exists()
    assert done_msg.output_path.name == output_filename(FIXTURE)
    # validator 결과도 첨부되어야 함
    assert done_msg.validation_report is not None
    assert done_msg.validation_report.passed, (
        f"IBK 기본 검증이 실패: {done_msg.validation_report.summary_line()}"
    )


def test_worker_reports_error_for_missing_input(tmp_path):
    q: queue.Queue = queue.Queue()
    req = PipelineRequest(
        input_path=tmp_path / "nope.docx",
        output_dir=tmp_path,
        template_path=template_path(),
    )
    t = run_pipeline_async(req, q)
    t.join(timeout=10)
    assert not t.is_alive()

    msgs = []
    while not q.empty():
        msgs.append(q.get_nowait())
    assert any(m.level == "error" for m in msgs)


def test_output_filename_contains_stem_and_date():
    name = output_filename(Path("IBK_샘플.docx"))
    assert name.startswith("IBK_샘플_output_")
    assert name.endswith(".xlsx")
    assert len(name) == len("IBK_샘플_output_YYYYMMDD.xlsx")
