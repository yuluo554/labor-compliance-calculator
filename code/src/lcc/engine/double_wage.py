"""未签书面劳动合同二倍工资引擎（plan/04 §6）——M3 实现。

公式依据：
  1. 起算：用工满 ``double_wage.start_after_months`` 个月的次日起
  2. 上限：最长 ``double_wage.max_months`` 个月
  3. 差额：逐月输出 ``{month, due, paid, difference}``，已支付部分冲抵
"""

from __future__ import annotations

from ..errors import NotImplementedYet

MILESTONE = "M3"


def compute(facts, ruleset):
    # type: (object, object) -> dict
    """计算二倍工资差额；返回计算区间 + 逐月明细 + ``basis``。实现里程碑：M3。"""
    raise NotImplementedYet(
        "二倍工资引擎将在 {} 实现（公式见 plan/04 §6）".format(MILESTONE)
    )


__all__ = ["MILESTONE", "compute"]