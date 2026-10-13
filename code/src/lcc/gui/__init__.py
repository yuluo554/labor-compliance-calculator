"""桌面界面（PySide6）——M5 实现。

M0 骨架阶段仅保留包结构，界面在 M5 落地。纪律（plan/03 §五、D-13）：
  * GUI 层**零判定逻辑**——只消费 :mod:`lcc.pipeline` 的编排结果；
  * PySide6 一律**惰性导入**（缺依赖时 CLI 打印安装提示 exit 2，不崩溃）。
"""

from __future__ import annotations

from ..errors import NotImplementedYet

MILESTONE = "M5"

__all__ = ["MILESTONE", "NotImplementedYet"]