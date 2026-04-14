"""
파일 기반 로깅.

위치:
  - Windows: %LOCALAPPDATA%\\chaekmu-parser\\logs\\YYYY-MM-DD.log
  - 기타:    ~/.chaekmu-parser/logs/YYYY-MM-DD.log

용량/보관:
  - 날짜별 파일 (TimedRotatingFileHandler 일 단위 7일 보관)
  - UTF-8, traceback 포함
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOGGER_NAME = "chaekmu_parser"


def log_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path.home() / ".chaekmu-parser"
    d = base / "chaekmu-parser" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def current_log_file() -> Path:
    return log_dir() / f"{datetime.now().strftime('%Y-%m-%d')}.log"


def setup_logging() -> logging.Logger:
    """최초 1회 호출 — 핸들러 중복 설정 방지."""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = TimedRotatingFileHandler(
        filename=str(current_log_file()),
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # 콘솔 (dev 실행 시만 의미 있음; PyInstaller --noconsole 빌드에선 무음)
    if sys.stdout is not None:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)

    logger.debug("logging initialized -> %s", current_log_file())
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


# ---------------------------------------------------------------------------
# 친화적 오류 메시지 변환
# ---------------------------------------------------------------------------
_FRIENDLY_MESSAGES = {
    "PackageNotFoundError": "Word 문서를 열 수 없습니다. 파일이 손상되었거나 .docx 형식이 아닐 수 있습니다.",
    "BadZipFile": "파일 형식이 올바르지 않습니다 (.docx 파일이 맞는지 확인해 주세요).",
    "PermissionError": "파일을 여는 중 권한 문제가 발생했습니다. 다른 프로그램에서 파일을 열고 있지 않은지 확인해 주세요.",
    "FileNotFoundError": "파일을 찾을 수 없습니다.",
    "KeyError": "예상된 데이터 구조가 누락되었습니다 (템플릿 또는 입력 파일 구조를 확인해 주세요).",
}


def friendly_error(exc: BaseException) -> str:
    name = type(exc).__name__
    msg = _FRIENDLY_MESSAGES.get(name)
    if msg:
        return f"❌ {msg}"
    return f"❌ {name}: {exc}"
