#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GUI offscreen 冒烟（CI 用）：真实构造窗口 + 触发计算 + 导出报告。

与 ``code/tests/test_gui_layer.py`` 的 offscreen 用例互补：
  * 测试给的是"能过/不能过"的信号（含负例与断言）；
  * 本脚本给的是**开发期可手动复跑的可见证据**（打印每步结果），
    且不依赖 pytest——CI 里作为独立步骤跑，任何一步失败即非零退出。

用法：
    QT_QPA_PLATFORM=offscreen py -X utf8 tools/gui_smoke.py
"""

from __future__ import annotations

import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "code", "src"))

# Qt 平台插件必须在创建 QApplication 之前选定
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


def main():
    # type: () -> int
    _ensure_utf8_stdio()

    try:
        from PySide6 import QtWidgets
    except ImportError as exc:
        sys.stderr.write(
            "GUI 冒烟需要 PySide6（gui extra）：\n"
            "    python -m pip install -e \"./code[gui]\"\n"
            "（原因：{}）\n".format(exc)
        )
        return 2

    from lcc.gui import app as gui_app

    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = gui_app.build_window(DATA_DIR)
    try:
        tabs = [window._tabs.tabText(i) for i in range(window._tabs.count())]
        sys.stdout.write("页签（{}）: {}\n".format(len(tabs), " / ".join(tabs)))
        for _key, label in gui_app._MODULE_TABS:
            if label not in tabs:
                sys.stderr.write("缺少模块页签: {}\n".format(label))
                return 1
        for required in ("参数库", "报告", "适用依据"):
            if required not in tabs:
                sys.stderr.write("缺少页签: {}\n".format(required))
                return 1

        result = window.compute()
        if result is None:
            sys.stderr.write("示例输入计算失败: {}\n".format(window._status.text()))
            return 1
        sys.stdout.write("计算坐标: {} / {} 年\n".format(*result.coordinate))

        for key, label in gui_app._MODULE_TABS:
            text = window._browsers[key].toPlainText()
            if not text.strip():
                sys.stderr.write("页签 {} 为空\n".format(label))
                return 1
            sys.stdout.write("[OK] {} 页签 {} 字符\n".format(label, len(text)))

        report_text = window._report_browser.toPlainText()
        if "免责声明" not in report_text:
            sys.stderr.write("报告页签缺少免责声明\n")
            return 1
        sys.stdout.write("[OK] 报告页签 {} 字符（含免责声明）\n".format(len(report_text)))

        # 导出两格式（GUI 与 CLI 共用 report 模块）
        from lcc.report import write_report

        with tempfile.TemporaryDirectory(prefix="lcc-gui-smoke-") as tmp:
            md_path = write_report(result, os.path.join(tmp, "out.md"))
            sys.stdout.write("[OK] 导出 Markdown: {} 字节\n".format(
                os.path.getsize(md_path)))
            try:
                xlsx_path = write_report(result, os.path.join(tmp, "out.xlsx"))
                sys.stdout.write("[OK] 导出 XLSX: {} 字节\n".format(
                    os.path.getsize(xlsx_path)))
            except Exception as exc:  # noqa: BLE001 - XLSX 为可选依赖，缺装不算失败
                sys.stdout.write("[SKIP] XLSX 导出不可用（可选依赖）: {}\n".format(exc))
    finally:
        window.close()

    sys.stdout.write("GUI_OFFSCREEN_SMOKE_OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
