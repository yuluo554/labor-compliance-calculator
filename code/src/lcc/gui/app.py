"""GUI 应用入口——M5 实现。

``lcc gui`` 经此模块启动。M0 阶段明确抛 :class:`~lcc.errors.NotImplementedYet`
（exit 1）并给出里程碑提示，**不静默启动一个空窗口**。
"""

from __future__ import annotations

from ..errors import NotImplementedYet
from . import MILESTONE


def run(data_dir=None):
    # type: (object) -> int
    """启动桌面界面。实现里程碑：M5。"""
    raise NotImplementedYet(
        "桌面界面将在 {} 实现（计划见 plan/05 M5；编排层 lcc.pipeline 已就位，"
        "界面只消费其输出）".format(MILESTONE)
    )


__all__ = ["run"]