"""IBK DOCX → XLSX 전체 파이프라인 1회 실행 (수동 검수용)."""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from chaekmu_parser.extractors.docx_extractor import DocxExtractor
from chaekmu_parser.normalizer import normalize
from chaekmu_parser.xlsx_writer import write

ROOT = Path(__file__).parent.parent
INPUT = ROOT / "fixtures/ibk/input.docx"
TEMPLATE = ROOT / "templates/chaekmu_template.xlsx"
OUTPUT = Path.home() / "Desktop" / "IBK_파이프라인_출력.xlsx"


def main() -> None:
    print(f"[1/3] Extracting  {INPUT}")
    raw = DocxExtractor().extract(INPUT)
    print(f"      top-level tables: {len(raw.tables)}")

    print("[2/3] Normalizing")
    parsed = normalize(raw)
    print(f"      executives: {parsed.parse_info.executive_count}")
    for i, e in enumerate(parsed.executives, 1):
        print(
            f"        {i:2d}. {e.position[:30]:30s} | "
            f"회의체 {len(e.committees)}, 책무 {len(e.responsibilities)}, "
            f"관리의무 {len(e.obligations)}"
        )

    print(f"[3/3] Writing XLSX  {OUTPUT}")
    write(parsed, TEMPLATE, OUTPUT)
    print(f"      done: {OUTPUT}")


if __name__ == "__main__":
    main()
