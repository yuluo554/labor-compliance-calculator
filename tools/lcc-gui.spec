# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec：GUI 窗口 exe（onedir，``console=False``）——M5-5（D-19）。

datas 白名单**唯一来源**是 :func:`lcc.packaging.build_datas`：本 spec 不内联任何
文件清单，避免两个 spec 各写一份导致漂移。

构建（于仓库根执行）：
    py -X utf8 -m PyInstaller --noconfirm --clean tools/lcc-gui.spec
产物：``dist/lcc-gui/``（onedir，含 ``_internal/data``）。
"""

import os
import sys

# SPECPATH = 本 spec 所在目录（tools/）；仓库根在其上一级
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, os.path.join(ROOT, "code", "src"))

from lcc.packaging import build_datas  # noqa: E402

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "tools", "entry_gui.py")],
    pathex=[os.path.join(ROOT, "code", "src")],
    binaries=[],
    datas=build_datas(ROOT),
    hiddenimports=["lcc.gui.app", "lcc.report.xlsx"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "unittest", "pydoc_data", "PIL", "lxml"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
# PyInstaller 5.x 有 zipped_data/zipfiles，6.x 已并入 datas/binaries：
# 用 getattr 兜底，让同一份 spec 在 5.x 与 6.x 都能跑（D-19 的单一源纪律不因版本分叉）。
pyz = PYZ(a.pure, getattr(a, "zipped_data", []), cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="lcc-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name="lcc-gui",
)
