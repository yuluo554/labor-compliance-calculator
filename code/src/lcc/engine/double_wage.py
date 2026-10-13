"""未签书面劳动合同二倍工资引擎（plan/04 §6）——M3 实现。

公式依据（数值一律取自 ``EffectiveRuleset``，禁止硬编码）：

  1. 起算：用工满 ``double_wage.start_after_months`` 个月的**次日**
     （plan/04 §6）
  2. 上限：自用工之日起满 ``start_after_months + max_months`` 个月之日为
     硬性截止（即「不满一年」前一日，最长 ``max_months`` 个月）；
     终止日期早于该日则按终止日期截断（plan/04 §6）
  3. 差额：``monthly_wage``（``avg_wage_months`` 个月平均应得工资）×
     区间月数 × ``double_wage.difference_multiple``（已付一倍，另付差额）
  4. 已签书面合同 → 差额为 0（附说明）

本模块是**独立于真值语义**的第二实现：真值单一实现源在
:mod:`lcc.benchmark.cases`（M1 冻结产物），对账由 ``benchmark.cases.compare``
完成——两实现逐字段一致才算通过（plan/05 §四.2）。
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..decimalutil import quantize_money
from ..errors import InputError

MILESTONE = "M3"

_ZERO = Decimal(0)

_BASIS = ["LCL-82"]


def _days_in_month(year, month):
    # type: (int, int) -> int
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _add_months(day, months):
    # type: (date, int) -> date
    """加 ``months`` 个日历月；目标月无该日时取该月最后一天（月末夹取）。"""
    total = day.month - 1 + int(months)
    year = day.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(day.day, _days_in_month(year, month)))


def _months_and_remainder(start, end):
    # type: (date, date) -> tuple
    """``(完整月数, 余日)``；``end < start`` 时完整月数为负。"""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if _add_months(start, months) > end:
        months -= 1
    anchor = _add_months(start, months)
    return months, (end - anchor).days


def _monthly_average(wages, ruleset):
    # type: (list, object) -> Decimal
    """二倍工资基数：``avg_wage_months`` 个月平均应得工资（不足按实际月份）。"""
    window = int(ruleset.avg_wage_months())
    sample = wages[-window:] if len(wages) > window else wages
    return sum(sample) / Decimal(len(sample))


def compute(facts, ruleset):
    # type: (object, object) -> dict
    """计算未签书面劳动合同二倍工资差额。

    :returns: 已签时 ``{signed: True, months: 0, total_difference: 0.00,
        amount: 0.00, steps, basis}``；未签时另含 ``start_date`` / ``end_date`` /
        ``monthly_wage`` / ``monthly_detail``（逐月明细）。
    """
    if facts.contract_signed:
        return {
            "signed": True,
            "months": 0,
            "total_difference": quantize_money(_ZERO),
            "amount": quantize_money(_ZERO),
            "steps": ["已订立书面劳动合同 → 不产生二倍工资差额"],
            "basis": list(_BASIS),
        }

    wages = list(facts.monthly_wages)
    if not wages:
        raise InputError("二倍工资计算需要 monthly_wages（月工资序列）")

    hire = facts.hire_date
    start_after = int(ruleset.double_wage_start_after_months())
    max_months = int(ruleset.double_wage_max_months())

    start = _add_months(hire, start_after) + timedelta(days=1)   # 满一个月的次日
    hard_end = _add_months(hire, start_after + max_months)       # 满一年之日（上限）
    end = facts.terminate_date or hard_end
    if end > hard_end:
        end = hard_end

    if end < start:
        months_count = 0
    else:
        months_count = _months_and_remainder(start, end)[0] + 1   # 首尾含当月

    monthly = _monthly_average(wages, ruleset)
    difference = monthly * months_count * ruleset.double_wage_difference_multiple()

    detail = [
        {
            "month": _add_months(start, index).strftime("%Y-%m"),
            "due": quantize_money(monthly),
            "paid": quantize_money(_ZERO),
            "difference": quantize_money(monthly * ruleset.double_wage_difference_multiple()),
        }
        for index in range(months_count)
    ]

    steps = _build_steps(hire, start, end, months_count, monthly, difference)
    return {
        "signed": False,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "months": months_count,
        "monthly_wage": quantize_money(monthly),
        "monthly_detail": detail,
        "total_difference": quantize_money(difference),
        "amount": quantize_money(difference),
        "steps": steps,
        "basis": list(_BASIS),
    }


def _build_steps(hire, start, end, months_count, monthly, difference):
    # type: (date, date, date, int, object, object) -> list
    """计算过程留痕（报告「逐项计算过程」用；数值均为运行时动态值）。"""
    return [
        "用工之日：{}；起算日（满一个月次日）：{}".format(hire.isoformat(), start.isoformat()),
        "计算区间：{} 至 {}（上限为用工满一年之日）".format(start.isoformat(), end.isoformat()),
        "区间月数（首尾含当月）：{} 个月".format(months_count),
        "月工资基数：{} 元 → 二倍工资差额 = 基数 × 月数 × 差额倍数 = {} 元".format(
            quantize_money(monthly), quantize_money(difference)),
    ]


__all__ = ["MILESTONE", "compute"]
