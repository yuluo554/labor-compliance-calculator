"""加班费引擎（plan/04 §4）——M3 实现。

公式依据：
  1. 工时制度门控：标准 / 综合计算 / 不定时（plan/04 §4.1）
  2. 三档倍率：工作日延长 / 休息日不能补休 / 法定节假日（plan/04 §4.2，
     倍率取自常数包 ``overtime.rates.*``）
  3. 计算基数口径规则化；低于最低工资时按最低工资（plan/04 §4.3）
  4. 法定节假日日历来自**该年度该地区**参数包（跨年度使用报错）
"""

from __future__ import annotations

from ..errors import NotImplementedYet

MILESTONE = "M3"

RATE_KIND_BY_DAY_TYPE = {
    "statutory_holiday": "statutory_holiday",
    "rest_day": "rest_day_no_compensatory",
    "workday": "workday_extension",
}


def compute(facts, ruleset):
    # type: (object, object) -> dict
    """计算加班费；返回逐条明细 + 合计 + ``basis``。实现里程碑：M3。"""
    raise NotImplementedYet(
        "加班费引擎将在 {} 实现（公式见 plan/04 §4）".format(MILESTONE)
    )


__all__ = ["MILESTONE", "RATE_KIND_BY_DAY_TYPE", "compute"]