# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：CLI 控制台 exe（onedir，``console=True``）——M5-5（D-19）。

datas 白名单**唯一来源**是 :func:`lcc.packaging.build_datas`（与 GUI spec 同源）。

构建（于仓库根执行）：
    py -X utf8 -m PyInstaller --noconfirm --clean tools/lcc-cli.spec
产物：``dist/lcc-cli/``（onedir，含 ``_internal/data``）。
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, os.path.join(ROOT, "code", "src"))

from lcc.packaging import build_datas  # noqa: E402

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "tools", "entry_cli.py")],
    pathex=[os.path.join(ROOT, "code", "src")],
    binaries=[],
    datas=build_datas(ROOT),
    hiddenimports=["lcc.report.xlsx"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "tkinter", "unittest", "pydoc_data"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, getattr(a, "zipped_data", []), cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="lcc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    getattr(a, "zipfiles", []),
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="lcc-cli",
)
