"""未休年休假折算引擎（plan/04 §5）——M3 实现。

公式依据（数值一律取自 ``EffectiveRuleset``，禁止硬编码）：

  1. 应休天数：按累计工作年限落入 ``annual_leave.entitlement_tiers`` 分档
     （plan/04 §5.1）
  2. 当年度折算：``elapsed_days``（当年度在本单位已过日历天数，含终止当日）
     ÷ ``annual_leave.days_per_year`` × 应休天数（plan/04 §5.2；折算应休天数
     保留原值供报告展示）
  3. 未休折算与冲抵：日工资 = 月工资 ÷ ``annual_leave.monthly_pay_days``；
     未休天数 = ``floor(折算应休天数 − 当年度已安排天数)``，下限截 0
     （R-02 已闭环，plan/06 D-31）；另付金额 = 日工资 × 未休天数 ×
     ``unused_multiple`` − 日工资 × 未休天数 × ``already_paid_portion``
     （实际另付部分，plan/04 §5.3）

本模块是**独立于真值语义**的第二实现：真值单一实现源在
:mod:`lcc.benchmark.cases`（M1 冻结产物），对账由 ``benchmark.cases.compare``
完成——两实现逐字段一致才算通过（plan/05 §四.2）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_FLOOR

from ..decimalutil import quantize_money
from ..errors import InputError

MILESTONE = "M3"

_ZERO = Decimal(0)

_BASIS = ["ALR-3", "ALR-5", "MOHRSS-ORDER-1-ART10", "MOHRSS-ORDER-1-ART11",
          "MOHRSS-ORDER-1-ART12"]


def _entitlement_days(service_years, ruleset):
    # type: (object, object) -> object
    """累计工作年限 → 年度应休天数（分档取自常数包）。

    累计工作不满最低分档下限（未满 1 年）→ 不享受年休假（应休 0 天，
    依《职工带薪年休假条例》第三条的享受条件）。
    """
    for tier in ruleset.entitlement_tiers():
        low = tier["min_service_years"]
        high = tier["max_service_years_exclusive"]
        if service_years >= low and (high is None or service_years < high):
            return tier["days"]
    return _ZERO


def _monthly_average(wages, ruleset):
    # type: (list, object) -> Decimal
    """年休假日工资基数：``avg_wage_months`` 个月平均应得工资（不足按实际）。"""
    window = int(ruleset.avg_wage_months())
    sample = wages[-window:] if len(wages) > window else wages
    return sum(sample) / Decimal(len(sample))


def compute(facts, ruleset):
    # type: (object, object) -> dict
    """计算未休年休假折算；返回天数 + 日工资 + 应付金额 + ``basis``。

    :returns: ``{entitlement_days, prorated_days, taken_days, unused_days,
        daily_wage, monthly_wage, payable_total, already_paid, additional_due,
        amount, steps, basis}``
    """
    terminate_date = facts.terminate_date
    if terminate_date is None:
        raise InputError("年休假折算需要 terminate_date（当年度折算终点）")

    wages = list(facts.monthly_wages)
    if not wages:
        raise InputError("年休假折算需要 monthly_wages（月工资序列）")

    entitlement = _entitlement_days(facts.cumulative_service_years, ruleset)

    year_start = date(terminate_date.year, 1, 1)
    elapsed_days = (terminate_date - year_start).days + 1
    prorated = Decimal(elapsed_days) / ruleset.days_per_year() * entitlement

    unused_raw = prorated - facts.annual_leave_taken_days
    # R-02 已闭环（D-31）：不足 1 整天不计 → 向下取整，下限 0
    unused_days = unused_raw.to_integral_value(rounding=ROUND_FLOOR)
    if unused_days < _ZERO:
        unused_days = _ZERO

    monthly = _monthly_average(wages, ruleset)
    daily = monthly / ruleset.monthly_pay_days()

    payable_total = daily * unused_days * ruleset.unused_multiple()
    already_paid = daily * unused_days * ruleset.already_paid_portion()
    additional = payable_total - already_paid

    steps = _build_steps(entitlement, elapsed_days, prorated, facts.annual_leave_taken_days,
                         unused_days, monthly, daily, additional)
    return {
        "entitlement_days": entitlement,
        "prorated_days": prorated,
        "taken_days": facts.annual_leave_taken_days,
        "unused_days": unused_days,
        "daily_wage": daily,
        "monthly_wage": quantize_money(monthly),
        "payable_total": quantize_money(payable_total),
        "already_paid": quantize_money(already_paid),
        "additional_due": quantize_money(additional),
        "amount": quantize_money(additional),
        "steps": steps,
        "basis": list(_BASIS),
    }


def _build_steps(entitlement, elapsed_days, prorated, taken, unused, monthly, daily,
                 additional):
    # type: (object, int, object, object, object, object, object, object) -> list
    """计算过程留痕（报告「逐项计算过程」用；数值均为运行时动态值）。"""
    steps = ["年度应休天数（按累计工作年限分档）：{} 天".format(entitlement)]
    steps.append("当年度已过日历天数：{} 天 → 折算应休 {:.6f} 天".format(
        elapsed_days, prorated))
    steps.append("扣除当年度已安排 {} 天后，应休未休天数（向下取整）= {} 天".format(
        taken, unused))
    steps.append("日工资 = 月平均应得工资 {} 元 ÷ 月计薪天数 = {} 元".format(
        quantize_money(monthly), daily))
    steps.append("未休年休假工资报酬（另付部分）= 日工资 × 未休天数 ×（未休倍数 − 已付比例）= {} 元".format(
        quantize_money(additional)))
    return steps


__all__ = ["MILESTONE", "compute"]
