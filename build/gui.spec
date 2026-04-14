# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — chaekmu-parser GUI.

빌드:  pyinstaller build/gui.spec --clean --noconfirm
산출:  dist/chaekmu-parser/{chaekmu-parser.exe, _internal/, templates/}
"""
from pathlib import Path

HERE = Path(SPECPATH).resolve()           # noqa: F821 (PyInstaller 전역)
ROOT = HERE.parent

block_cipher = None

a = Analysis(
    [str(ROOT / "src" / "chaekmu_parser_gui" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "templates" / "chaekmu_template.xlsx"), "templates"),
    ],
    hiddenimports=[
        "chaekmu_parser_gui",
        "chaekmu_parser_gui.app",
        "chaekmu_parser_gui.workers",
        "chaekmu_parser_gui.logging_setup",
        "chaekmu_parser.extractors.docx_extractor",
        "chaekmu_parser.normalizer",
        "chaekmu_parser.validator",
        "chaekmu_parser.xlsx_writer",
        "customtkinter",
        # pyhwp는 Phase 2 착수 후 실제 동작 검증하여 추가 예정
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Phase 3 PDF 전까지 제외 — 번들 크기 절감
        "pdfplumber",
        "pdfminer",
        "pdfminer.six",
        "cryptography",
        "PIL",
        "pillow",
        "pypdfium2",
        # 개발 전용
        "pytest",
        "pytest_cov",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="chaekmu-parser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,      # GUI 전용 - 콘솔 창 숨김
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,          # 차기 반영 (claudedocs/gui_packaging_design.md §11)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="chaekmu-parser",
)
