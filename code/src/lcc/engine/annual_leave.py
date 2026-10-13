"""未休年休假折算引擎（plan/04 §5）——M3 实现。

公式依据：
  1. 应休天数：按累计工作年限落入 ``annual_leave.entitlement_tiers`` 分档
  2. 当年度折算：已过日历天数 ÷ ``days_per_year`` × 应休天数，取整口径挂依据
     （取整方向为缓议项 R-02，以《实施办法》原文核对后定稿）
  3. 未休折算与冲抵：日工资 = 月工资 ÷ ``monthly_pay_days``；
     未休部分按 ``unused_multiple`` 计，其中 ``already_paid_portion`` 已付 →
     实际另付部分 = 总额 − 已付
"""

from __future__ import annotations

from ..errors import NotImplementedYet

MILESTONE = "M3"


def compute(facts, ruleset):
    # type: (object, object) -> dict
    """计算未休年休假折算；返回 ``additional_due`` 等字段 + ``basis``。实现里程碑：M3。"""
    raise NotImplementedYet(
        "未休年休假折算引擎将在 {} 实现（公式见 plan/04 §5）".format(MILESTONE)
    )


__all__ = ["MILESTONE", "compute"]