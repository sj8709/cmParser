"""DocxExtractor._para_is_bold 회귀 — 한두 글자 우연 bold가 제목으로 오승격되지 않아야 함.

KDB IT부문장 실측 버그: 관리의무 세부항목 'IT 감리 프로젝트 대상 내·외부 감리 업무'에서
가운뎃점 '·' 1글자만 bold라, 기존 `any(run.bold)` 규칙이 단락 전체를 책무 제목으로 오승격.
이 테스트는 IBK fixture 없이도 항상 실행되도록 가짜 run 스텁으로 검증한다.
"""

from dataclasses import dataclass

from chaekmu_parser.extractors.docx_extractor import DocxExtractor


@dataclass
class _Run:
    text: str
    bold: bool | None  # python-docx run.bold 는 True/False/None


class _Para:
    def __init__(self, runs: list[_Run]) -> None:
        self.runs = runs


def _para(*runs: tuple[str, bool | None]) -> _Para:
    return _Para([_Run(t, b) for t, b in runs])


def test_full_bold_single_run_is_bold():
    p = _para(("IT 자체감사 기획, 수행 및 관리에 대한 책임 ", True))
    assert DocxExtractor._para_is_bold(p) is True


def test_all_runs_bold_is_bold():
    # python-docx가 제목을 여러 run으로 쪼개도 전부 bold면 제목
    p = _para(
        ("IT ", True), ("표준", True), ("·", True),
        ("품질관리 및 IT 감리 운영에 대한 책임 ", True),
    )
    assert DocxExtractor._para_is_bold(p) is True


def test_stray_one_char_bold_is_not_bold():
    """실제 KDB 케이스: '·' 1글자만 bold인 세부항목 → 제목 아님."""
    p = _para(
        ("IT 감리", None),
        (" 프로젝트 대상 ", None),
        ("내", None),
        ("·", True),            # 잡티 bold 1글자
        ("외부", None),
        (" 감리 업무 ", None),
    )
    assert DocxExtractor._para_is_bold(p) is False


def test_all_nonbold_is_not_bold():
    p = _para(("IT 품질관리 및 서비스 개선관리, 이력 및 형상관리 ", None))
    assert DocxExtractor._para_is_bold(p) is False


def test_whitespace_only_bold_run_ignored():
    # 공백만 bold인 run은 가중치에서 제외 → 전체 non-bold
    p = _para(("세부 항목 텍스트", None), ("   ", True))
    assert DocxExtractor._para_is_bold(p) is False


def test_empty_paragraph_is_not_bold():
    assert DocxExtractor._para_is_bold(_para()) is False


def test_majority_bold_is_bold():
    # 번호 접두 등 일부 비-bold여도 본문 과반이 bold면 제목
    p = _para(("1. ", None), ("책무 제목 텍스트입니다", True))
    assert DocxExtractor._para_is_bold(p) is True
