"""
엔트리 포인트.

실행 방법:
    python -m chaekmu_parser_gui
    chaekmu-parser-gui              (pip install 후)
    chaekmu-parser.exe              (PyInstaller 빌드 후)
"""

from __future__ import annotations

import sys


def main() -> int:
    from chaekmu_parser_gui.app import MainWindow

    window = MainWindow()
    window.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
