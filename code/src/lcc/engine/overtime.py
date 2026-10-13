"""加班费引擎（plan/04 §4）——M3 实现。

公式依据：
  1. 工时制度门控：标准 / 综合计算 / 不定时（plan/04 §4.1）
  2. 三档倍率：工作日延长 / 休息日不能补休 / 法定节假日（plan/04 §4.2，
     倍率取自常数包 ``overtime.rates.*``）
  3. 计算基数口径规则化；低于最低工资时按最低工资（plan/04 §4.3）
  4. 日期类型由**该年度该地区**参数包的日历单点判定
     （``ruleset.holiday_day_type``），跨年度使用报错
"""

from __future__ import annotations

from ..errors import NotImplementedYet

MILESTONE = "M3"

# 日历日期类型 → 倍率档位（档位名取自常数包 overtime.rates.*）
# 调休上班日（原休息日改为工作日）在法律性质上仍是"休息日工作"，
# 未安排补休时按休息日口径计。
RATE_KIND_BY_DAY_TYPE = {
    "statutory_holiday": "statutory_holiday",
    "rest_day": "rest_day_no_compensatory",
    "adjusted_workday": "rest_day_no_compensatory",
    "workday": "workday_extension",
}


def compute(facts, ruleset):
    # type: (object, object) -> dict
    """计算加班费；返回逐条明细 + 合计 + ``basis``。实现里程碑：M3。"""
    raise NotImplementedYet(
        "加班费引擎将在 {} 实现（公式见 plan/04 §4）".format(MILESTONE)
    )


__all__ = ["MILESTONE", "RATE_KIND_BY_DAY_TYPE", "compute"]