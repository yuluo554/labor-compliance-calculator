#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""演示素材生成（M5-4）：GUI 截图 PNG + 操作演示 GIF → ``docs/demo/``。

纪律：
  * **全离线**：offscreen Qt 渲染，不弹真实窗口、不联网；
  * **脱敏**：素材只用仓库内示例输入（虚构「示例员工」与虚构工资序列），
    不含任何真实个人信息；生成后由 ``tools/dessensitize_audit.py`` 复核；
  * **可复现**：帧序列与导出顺序固定；GIF 采用固定调色板与循环参数，
    同一版本重跑产出**逐字节一致**（Pillow 的 ``duration``/``loop`` 固定，
    不写入当前时间）。

用法：
    py -X utf8 tools/make_demo_assets.py                  # 生成全部素材
    py -X utf8 tools/make_demo_assets.py --out docs/demo  # 指定输出目录
    py -X utf8 tools/make_demo_assets.py --list           # 只列将产出的文件

依赖：``PySide6``（gui extra）+ ``Pillow``（仅 GIF 合成用；缺失时只出 PNG）。
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "code", "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from lcc._stdio import _ensure_utf8_stdio
except ImportError:  # 兜底：脱离仓库布局
    def _ensure_utf8_stdio(stream_names=("stdout", "stderr")):
        # type: (object) -> None
        for name in stream_names:
            stream = getattr(sys, name, None)
            if stream is None:
                continue
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8")
                except (ValueError, OSError):
                    pass

DATA_DIR = os.path.join(ROOT, "data")
DEFAULT_OUT = os.path.join(ROOT, "docs", "demo")

# 帧定义：``(输出文件名, 动作, 说明)``——动作是为了让 GIF 呈现"点算 → 切页签"的流程
FRAMES = (
    ("01-input.png", "input", "输入事实（示例员工，虚构数据）"),
    ("02-severance.png", "tab:0", "经济补偿/赔偿金页签"),
    ("03-overtime.png", "tab:1", "加班费页签（日历四类联动）"),
    ("04-annual-leave.png", "tab:2", "未休年休假页签（折算 + 向下取整）"),
    ("05-double-wage.png", "tab:3", "二倍工资页签（起算 + 逐月明细）"),
    ("06-params.png", "tab:4", "参数库页签（坐标与核对状态）"),
    ("07-report.png", "tab:5", "报告页签（含免责声明与参数来源）"),
    ("08-basis.png", "tab:6", "适用依据页签"),
)

GIF_NAME = "demo.gif"
GIF_FRAME_MS = 1400
GIF_SIZE = (1024, 820)

# 候选系统 CJK 字体（offscreen 平台不会自动扫描系统字体目录，中文会渲染成豆腐块）。
# Windows 侧由 ``WINDIR``/``SystemRoot`` 环境变量推导字体目录——避免在源码里写死
# 绝对盘符路径（脱敏审计会把它当"其他盘路径"复核项，且换机即失效）。
_WINDOWS_FONT_FILES = ("msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc")
_POSIX_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def _cjk_font_candidates():
    # type: () -> list
    """候选字体绝对路径：Windows 由系统目录环境变量推导，POSIX 用常见发行版路径。"""
    candidates = []
    for variable in ("WINDIR", "SystemRoot"):
        root = os.environ.get(variable)
        if root:
            for name in _WINDOWS_FONT_FILES:
                candidates.append(os.path.join(root, "Fonts", name))
    candidates.extend(_POSIX_FONT_PATHS)
    return candidates


def _require_pyside():
    # type: () -> tuple
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError as exc:
        sys.stderr.write(
            "生成演示素材需要 PySide6（gui extra）：\n"
            "    python -m pip install -e \"./code[gui]\"\n"
            "（原因：{}）\n".format(exc)
        )
        raise SystemExit(2)
    return QtCore, QtGui, QtWidgets


def _install_cjk_font(QtGui, QtWidgets):
    # type: (object, object) -> str
    """显式加载一个 CJK 字体并设为应用默认族。

    offscreen 平台下 Qt 找不到系统字体目录（Qt 6 起不再随附字体），中文会渲染成
    豆腐块——Demo 素材必须可读，故此处按候选路径显式加载。
    """
    for path in _cjk_font_candidates():
        if not os.path.isfile(path):
            continue
        font_id = QtGui.QFontDatabase.addApplicationFont(path)
        if font_id < 0:
            continue
        families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            continue
        font = QtGui.QFont(families[0])
        QtWidgets.QApplication.setFont(font)
        return families[0]
    sys.stderr.write("警告：未找到可加载的 CJK 字体，截图中的中文可能显示为方块。\n")
    return ""


def _capture(out_dir, with_gif=True):
    # type: (str, bool) -> list
    QtCore, QtGui, QtWidgets = _require_pyside()
    from lcc.gui import app as gui_app

    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    family = _install_cjk_font(QtGui, QtWidgets)
    if family:
        sys.stdout.write("使用字体: {}\n".format(family))
    window = gui_app.build_window(DATA_DIR)
    window.resize(*GIF_SIZE)
    window.show()

    written = []
    for name, action, _label in FRAMES:
        if action == "input":
            window.reset_form()
        elif action.startswith("tab:"):
            window.compute()
            window._tabs.setCurrentIndex(int(action.split(":")[1]))
        application.processEvents()

        path = os.path.join(out_dir, name)
        pixmap = window.grab()
        pixmap.save(path, "PNG")
        written.append(path)

    if with_gif:
        written.append(_build_gif(out_dir, [os.path.join(out_dir, item[0]) for item in FRAMES]))

    window.close()
    return written


def _build_gif(out_dir, frame_paths):
    # type: (str, list) -> str
    """把 PNG 帧序列合成为循环 GIF（固定时长/调色板 → 可复现）。"""
    try:
        from PIL import Image
    except ImportError:
        sys.stderr.write(
            "未安装 Pillow，跳过 GIF 合成（PNG 截图已生成）。\n"
            "    python -m pip install Pillow\n"
        )
        return ""

    frames = []
    for path in frame_paths:
        if not os.path.isfile(path):
            continue
        image = Image.open(path).convert("RGB")
        image = image.resize(GIF_SIZE, Image.LANCZOS)
        frames.append(image.quantize(colors=256))
    if not frames:
        return ""

    gif_path = os.path.join(out_dir, GIF_NAME)
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=GIF_FRAME_MS,
        loop=0,
        optimize=False,
    )
    return gif_path


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="生成 GUI 演示素材（PNG + GIF）")
    parser.add_argument("--out", default=DEFAULT_OUT, help="输出目录（默认 docs/demo）")
    parser.add_argument("--list", action="store_true", help="只列出将产出的文件")
    parser.add_argument("--no-gif", action="store_true", help="只生成 PNG 截图")
    args = parser.parse_args(argv)

    out_dir = os.path.abspath(args.out)
    planned = [os.path.join(out_dir, item[0]) for item in FRAMES]
    if not args.no_gif:
        planned.append(os.path.join(out_dir, GIF_NAME))

    if args.list:
        for path in planned:
            sys.stdout.write("{}\n".format(os.path.relpath(path, ROOT).replace("\\", "/")))
        return 0

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    written = _capture(out_dir, with_gif=not args.no_gif)
    for path in written:
        if path:
            sys.stdout.write("已生成 {}\n".format(
                os.path.relpath(path, ROOT).replace("\\", "/")))
    sys.stdout.write("DEMO_ASSETS_OK（{} 个文件）\n".format(len([p for p in written if p])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
