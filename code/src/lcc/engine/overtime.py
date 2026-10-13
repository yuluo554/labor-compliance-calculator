"""加班费引擎（plan/04 §4）——M3 实现。

公式依据（数值一律取自 ``EffectiveRuleset``，禁止硬编码）：

  1. 计算基数：劳动者月工资（``avg_wage_months`` 个月平均应得工资，D-32/D-33）；
     低于 ``min_wage_monthly`` 时取下限（plan/04 §4.2）
  2. 小时工资：基数 ÷（``annual_leave.monthly_pay_days`` ×
     ``overtime.standard_daily_hours``）——两值均来自常数包（plan/04 §4.2）
  3. 日期类型由**该年度该地区**参数包的日历单点判定
     （``ruleset.holiday_day_type``，四类：法定节假日 / 休息日 / 调休上班日 /
     普通工作日，plan/04 §4.3）；引擎**不得自建日历逻辑**
  4. 三档倍率取自常数包 ``overtime.rates.*``：法定节假日最高档 / 休息日与
     调休上班日（未补休）次之 / 工作日延长最低档（具体数值只在数据包，不在本文件）
  5. 显式 ``kind`` 覆盖日历判定（plan/04 §4.3）：条目自带 ``kind != auto`` 时，
     按该 kind 对应的档位计——真值库当前全部为 ``auto``，覆盖通路由单测覆盖

工时制度（standard/comprehensive/irregular）在 v1 为**记录性字段**：三档倍率一律
由日历 + 常数包决定，不随工时制度变化（R-03 闭环见 plan/06 D-41：不定时工作制的
地区性例外无全国统一口径，留待逐地区参数化）。

本模块是**独立于真值语义**的第二实现：真值单一实现源在
:mod:`lcc.benchmark.cases`（M1 冻结产物），对账由 ``benchmark.cases.compare``
完成——两实现逐字段一致才算通过（plan/05 §四.2）。
"""

from __future__ import annotations

from decimal import Decimal

from ..decimalutil import quantize_money
from ..errors import InputError

MILESTONE = "M3"

_ZERO = Decimal(0)

# 日历日期类型 → 倍率档位（档位名取自常数包 overtime.rates.*）
# 调休上班日（原休息日改为工作日）在法律性质上仍是"休息日工作"，
# 未安排补休时按休息日口径计。
RATE_KIND_BY_DAY_TYPE = {
    "statutory_holiday": "statutory_holiday",
    "rest_day": "rest_day_no_compensatory",
    "adjusted_workday": "rest_day_no_compensatory",
    "workday": "workday_extension",
}

# 显式 kind（输入断言）→ 日历日期类型（复用同一档位映射，避免第二份口径）
_KIND_TO_DAY_TYPE = {
    "workday_extension": "workday",
    "rest_day": "rest_day",
    "statutory_holiday": "statutory_holiday",
}

_BASIS = ["LL-44", "LL-36"]


def _monthly_average(wages, ruleset):
    # type: (list, object) -> Decimal
    """加班基数：``avg_wage_months`` 个月平均应得工资（不足则按实际月份）。"""
    window = int(ruleset.avg_wage_months())
    sample = wages[-window:] if len(wages) > window else wages
    return sum(sample) / Decimal(len(sample))


def _day_type_for(item, ruleset):
    # type: (object, object) -> tuple
    """返回 ``(day_type, source)``；``auto`` 走日历单点，显式 kind 走断言映射。"""
    kind = getattr(item, "kind", "auto")
    if kind == "auto":
        return ruleset.holiday_day_type(item.date.isoformat()), "calendar"
    return _KIND_TO_DAY_TYPE[kind], "explicit"


def compute(facts, ruleset):
    # type: (object, object) -> dict
    """计算加班费；返回逐条明细 + 合计 + ``basis``。

    :returns: ``{hourly_base, min_wage_applied, entries, total, amount, steps,
        basis}``；``entries`` 逐条含 ``{date, day_type, rate, hours, entry_amount}``
        （``day_type`` 为日历四类；``rate`` 取自常数包）。
    """
    wages = list(facts.monthly_wages)
    if not wages:
        raise InputError("加班费计算需要 monthly_wages（月工资序列）")

    base = _monthly_average(wages, ruleset)
    min_wage = ruleset.min_wage_monthly()
    min_wage_applied = base < min_wage
    if min_wage_applied:
        base = min_wage

    hourly = base / ruleset.monthly_pay_days() / ruleset.overtime_standard_daily_hours()

    entries = []
    total = _ZERO
    for item in facts.overtime:
        day_type, source = _day_type_for(item, ruleset)
        rate = ruleset.overtime_rate(RATE_KIND_BY_DAY_TYPE[day_type])
        amount = hourly * item.hours * rate
        total = total + amount
        entries.append(
            {
                "date": item.date.isoformat(),
                "day_type": day_type,
                "rate": rate,
                "hours": item.hours,
                "entry_amount": quantize_money(amount),
                "day_type_source": source,
            }
        )

    steps = _build_steps(base, min_wage_applied, min_wage, hourly, entries, total)
    return {
        "hourly_base": hourly,
        "min_wage_applied": min_wage_applied,
        "entries": entries,
        "total": quantize_money(total),
        "amount": quantize_money(total),
        "work_system": getattr(facts, "work_system", "standard"),
        "steps": steps,
        "basis": list(_BASIS),
    }


def _build_steps(base, min_wage_applied, min_wage, hourly, entries, total):
    # type: (object, bool, object, object, list, object) -> list
    """计算过程留痕（报告「逐项计算过程」用；数值均为运行时动态值）。"""
    steps = ["加班基数：月平均应得工资 = {} 元".format(quantize_money(base))]
    if min_wage_applied:
        steps.append("最低工资下限生效：基数取 {} 元".format(min_wage))
    steps.append("小时工资 = 基数 ÷（月计薪天数 × 日标准工时）= {}".format(
        quantize_money(hourly)))
    steps.append("逐条按日历日期类型取倍率：{} 条".format(len(entries)))
    steps.append("加班费合计 = {}".format(quantize_money(total)))
    return steps


__all__ = ["MILESTONE", "RATE_KIND_BY_DAY_TYPE", "compute"]
