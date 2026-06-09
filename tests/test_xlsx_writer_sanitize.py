"""xlsx_writer._sanitize — MS949 비호환 문자 치환 검증."""

from chaekmu_parser.xlsx_writer import _sanitize


def test_middot_variants_unified_to_u00b7():
    src = "기획∙운영 • 관리 ‧ 점검 ⋅ 보고 ㆍ 자료"
    out = _sanitize(src)
    assert "∙" not in out and "•" not in out
    assert "‧" not in out and "⋅" not in out
    assert "ㆍ" not in out
    assert out.count("·") == 5


def test_curly_quotes_to_ascii():
    src = "“인용” ‘single’"
    out = _sanitize(src)
    assert out == '"인용" \'single\''


def test_nonstandard_spaces_to_ascii_space():
    src = "A B C D"
    assert _sanitize(src) == "A B C D"


def test_zero_width_chars_removed():
    src = "A​B‌C‍D﻿E"
    assert _sanitize(src) == "ABCDE"


def test_cp949_compatible_preserved():
    """em/en dash, 줄임표, U+00B7는 CP949에 매핑되어 보존."""
    src = "A—B–C…D·E"
    out = _sanitize(src)
    assert out == src


def test_output_encodes_to_ms949():
    """sanitize 결과 전체가 MS949(=CP949)로 인코딩 가능해야 한다."""
    src = (
        "혁신금융서비스 기획∙운영 • “테스트” "
        "‘인용’ NBSP​zwsp ⋅점검 ㆍ라ㆍ"
    )
    out = _sanitize(src)
    out.encode("ms949")  # raises UnicodeEncodeError on failure


def test_empty_and_none_safe():
    assert _sanitize("") == ""
    assert _sanitize(None) is None  # type: ignore[arg-type]
