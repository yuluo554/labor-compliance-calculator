"""报告导出（Markdown + XLSX）——M5 实现（FR-6）。

纪律：
  * 报告内容 = :class:`lcc.pipeline.CalcResult` 的渲染，**不新增任何判定**；
  * 必须含：输入事实、适用法条、逐项计算过程、**参数来源块**（哪年哪地社平工资）、
    结论区间、**免责声明**（FR-6.3）；
  * XLSX 为可选依赖（``openpyxl``，extra ``report``），缺失时降级为 Markdown 并提示。
"""

from __future__ import annotations

from ..errors import NotImplementedYet

MILESTONE = "M5"


def render_markdown(result):
    # type: (object) -> str
    """渲染 Markdown 测算说明。实现里程碑：M5。"""
    raise NotImplementedYet("Markdown 报告导出将在 {} 实现（FR-6）".format(MILESTONE))


def render_xlsx(result, path):
    # type: (object, str) -> str
    """渲染 XLSX 测算说明（需 openpyxl）。实现里程碑：M5。"""
    raise NotImplementedYet("XLSX 报告导出将在 {} 实现（FR-6）".format(MILESTONE))


__all__ = ["MILESTONE", "render_markdown", "render_xlsx"]