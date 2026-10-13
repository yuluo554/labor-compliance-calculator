#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PyInstaller 打包入口：GUI 窗口 exe（``console=False``，D-19）。

``--windowed`` 下无控制台，PySide6 缺失等致命错误无处打印；故此处捕获异常并弹
一个原生消息框（不依赖 Qt，避免"报错时依赖本身不可用"的死结）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code", "src"))

from lcc.errors import LccError  # noqa: E402


def _alert(message):
    # type: (str) -> None
    """弹原生消息框（tkinter 是 stdlib；GUI exe 里已随包）。"""
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("劳动用工合规计算引擎", message)
        root.destroy()
    except Exception:  # noqa: BLE001 - 兜底：连弹窗也不可用时写日志
        try:
            with open(os.path.join(os.path.expanduser("~"), "lcc-gui-error.log"),
                      "a", encoding="utf-8") as handle:
                handle.write(message + "\n")
        except OSError:
            pass


def main():
    # type: () -> int
    from lcc.errors import EXIT_INPUT_ERROR
    from lcc.gui.app import run

    try:
        return int(run())
    except LccError as exc:
        _alert(exc.render())
        return int(exc.exit_code)
    except Exception as exc:  # noqa: BLE001 - 窗口态必须把异常显示出来，否则"闪退无痕"
        _alert("启动失败：{}".format(exc))
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
