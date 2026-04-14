"""GUI 로깅/오류 처리 검증."""

import logging

import pytest

from chaekmu_parser_gui.logging_setup import (
    current_log_file,
    friendly_error,
    get_logger,
    log_dir,
    setup_logging,
)


def test_log_dir_exists_and_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    d = log_dir()
    assert d.exists()
    assert d.is_dir()
    # 쓰기 가능 확인
    (d / "smoke.tmp").write_text("ok", encoding="utf-8")


def test_setup_logging_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    # handlers를 비운 상태에서 setup
    logger = logging.getLogger("chaekmu_parser")
    for h in list(logger.handlers):
        logger.removeHandler(h)

    a = setup_logging()
    handlers_after_first = len(a.handlers)
    b = setup_logging()
    assert b is a
    assert len(b.handlers) == handlers_after_first, "setup_logging 재호출 시 핸들러 중복 등록"


def test_friendly_error_known_types():
    assert "Word 문서" in friendly_error(_make_exception("PackageNotFoundError"))
    assert "권한" in friendly_error(PermissionError("foo"))
    assert "찾을 수" in friendly_error(FileNotFoundError("foo"))


def test_friendly_error_unknown_falls_back_to_generic():
    class SomethingWeird(Exception):
        pass

    msg = friendly_error(SomethingWeird("detail"))
    assert "SomethingWeird" in msg
    assert "detail" in msg


def test_get_logger_writes_to_current_log_file(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    logger = logging.getLogger("chaekmu_parser")
    for h in list(logger.handlers):
        logger.removeHandler(h)

    setup_logging()
    get_logger().info("HELLO-FROM-TEST")
    for h in logger.handlers:
        h.flush()

    log_text = current_log_file().read_text(encoding="utf-8")
    assert "HELLO-FROM-TEST" in log_text


def _make_exception(class_name: str) -> Exception:
    """테스트용 — 실제 클래스가 없어도 이름만 갖는 예외 생성."""
    cls = type(class_name, (Exception,), {})
    return cls("stub")
