"""经济补偿 / 赔偿金引擎（plan/04 §3）——M2 实现。

公式依据（数值一律取自 ``EffectiveRuleset``，禁止硬编码；口径出处见 plan/06）：

  1. 口径判定：解除情形 → N / N+1 / 2N / none（plan/04 §3.1 映射表；D-30 代通知金）
  2. 工作年限取整：完整月数 + 余日（≥15 天计半个月，D-34）；满
     ``full_year_threshold_months`` 个月不满 1 年 → 按 1 年，否则按
     ``round_down_to_half_month``（plan/04 §3.2）
  3. 月工资：解除前 ``avg_wage_months`` 个月平均应得工资（D-32 剔除加班工资）；
     低于 ``min_wage_monthly`` 时按最低工资（plan/04 §3.3）
  4. 三倍封顶：月工资 > 社平工资 × ``cap_multiple_of_social_avg`` 时按封顶基数，
     且年限 ≤ ``cap_years``（plan/04 §3.4；**严格大于**，恰好等于不封顶）
  5. 金额：N = 基数 × 年限；N+1 = N + 代通知金（上一个月工资，不受封顶/下限约束）；
     2N = 基数 × 年限 × ``compensation_multiple``（plan/04 §3.5）

本模块是**独立于真值语义**的第二实现：真值单一实现源在
:mod:`lcc.benchmark.cases`（M1 冻结产物），对账由 ``benchmark.cases.compare``
完成——两实现逐字段一致才算通过（plan/05 §四.2「不许改真值凑引擎」）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_FLOOR

from ..decimalutil import quantize_money
from ..errors import ComputationError, InputError

MILESTONE = "M2"

_ZERO = Decimal(0)
_HALF = Decimal("0.5")
_TWELVE = Decimal(12)
# 余日折算阈值（天）：余日 ≥ 15 天计半个月，否则不计（既定计算口径 D-34；
# <100 属通用计算常量，零政策字面量门禁豁免）
_REMAINDER_HALF_MONTH_DAYS = 15

# 解除情形 → 口径（plan/04 §3.1；纯映射，无数值政策字面量）
FORMULA_BY_GROUND = {
    "mutual_agreement": "N",
    "employee_fault_dismissal": "none",
    "employer_unilateral_no_fault": "N",          # 未提前通知时由 notified 标志升级为 N+1
    "economic_layoff": "N",
    "illegal_termination": "2N",
    "contract_expiry_employer_no_renewal": "N",
    "employee_resignation_art38": "N",
    "employee_resignation_voluntary": "none",
}

FORMULA_CLAUSE_IDS = {
    "N": ["LCL-46", "LCL-47"],
    "N+1": ["LCL-40", "LCL-47"],
    "2N": ["LCL-48", "LCL-87"],
    "none": [],
}

_REASON_BY_GROUND = {
    "mutual_agreement": "协商一致解除（第 36 条）→ 应支付经济补偿",
    "employee_fault_dismissal": "劳动者过错解除（第 39 条）→ 无需支付经济补偿",
    "employer_unilateral_no_fault": "无过失性辞退（第 40 条）",
    "economic_layoff": "经济性裁员（第 41 条）→ 应支付经济补偿",
    "illegal_termination": "违法解除（第 48/87 条）→ 支付赔偿金",
    "contract_expiry_employer_no_renewal": "合同到期用人单位不续订（第 46 条第 5 项）→ 应支付经济补偿",
    "employee_resignation_art38": "劳动者被迫解除（第 38 条）→ 应支付经济补偿",
    "employee_resignation_voluntary": "劳动者主动辞职 → 无需支付经济补偿",
}


# --------------------------------------------------------------------------
# 日历算术（与真值语义独立实现；两路径一致由对账测试保证）
# --------------------------------------------------------------------------

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
    """``(完整月数, 余日)``；``end < start`` 报 :class:`ComputationError`。"""
    if end < start:
        raise ComputationError("终止日期早于起始日期，无法计算工作年限")
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if _add_months(start, months) > end:
        months -= 1
    anchor = _add_months(start, months)
    return months, (end - anchor).days


def service_years_for_compensation(hire_date, terminate_date, ruleset):
    # type: (date, date, object) -> Decimal
    """工作年限取整（plan/04 §3.2 + D-34）。

    完整月数 + 余日折算 → 按第 47 条取整：满 ``full_year_threshold_months``
    个月不满 1 年按 1 年；不满该阈值按 ``round_down_to_half_month``。
    """
    months, remainder = _months_and_remainder(hire_date, terminate_date)
    service_months = Decimal(months)
    if remainder >= _REMAINDER_HALF_MONTH_DAYS:
        service_months = service_months + _HALF

    full_years = (service_months / _TWELVE).to_integral_value(rounding=ROUND_FLOOR)
    rem_months = service_months - full_years * _TWELVE
    if rem_months >= ruleset.full_year_threshold_months():
        return full_years + ruleset.round_up_to_year()
    if rem_months > _ZERO:
        return full_years + ruleset.round_down_to_half_month()
    return full_years


# --------------------------------------------------------------------------
# 口径判定（FR-2.1 / 基准 B1）
# --------------------------------------------------------------------------

def determine_formula(termination):
    # type: (object) -> dict
    """口径判定：解除情形 → ``{"ground", "formula", "basis", "reason"}``。

    易混边界（进基准 B1 枚举）：
      * 第 40 条**未提前 30 日通知** → N+1（代通知金），**不是** 2N；
      * 第 39 条劳动者过错解除 → none（0），不是 N；
      * 第 38 条被迫解除 → N，不是 0。
    """
    ground = getattr(termination, "ground", None)
    if ground not in FORMULA_BY_GROUND:
        raise InputError("未知解除情形 {!r}".format(ground))

    if ground == "employer_unilateral_no_fault":
        if not termination.notified_30d_in_advance:
            formula = "N+1"
            reason = "无过失性辞退（第 40 条）且未提前 30 日通知 → 额外支付一个月工资（代通知金）"
        else:
            formula = "N"
            reason = "无过失性辞退（第 40 条）已提前 30 日通知 → 仅支付经济补偿"
    else:
        formula = FORMULA_BY_GROUND[ground]
        reason = _REASON_BY_GROUND[ground]

    return {
        "ground": ground,
        "formula": formula,
        "basis": list(FORMULA_CLAUSE_IDS[formula]),
        "reason": reason,
    }


# --------------------------------------------------------------------------
# 计算
# --------------------------------------------------------------------------

def _monthly_average(wages, ruleset):
    # type: (list, object) -> Decimal
    """解除前 ``avg_wage_months`` 个月平均应得工资（不足则按实际月份）。"""
    window = int(ruleset.avg_wage_months())
    sample = wages[-window:] if len(wages) > window else wages
    return sum(sample) / Decimal(len(sample))


def compute(facts, termination, ruleset):
    # type: (object, object, object) -> dict
    """计算经济补偿/赔偿金。

    :param facts: :class:`lcc.model.EmploymentFacts`（须含 ``terminate_date`` 与工资序列）
    :param termination: :class:`lcc.model.TerminationFacts`
    :param ruleset: :class:`lcc.gate.EffectiveRuleset`（门控产物；法定数值唯一来源）
    :returns: ``{formula, ground, service_years, monthly_wage_avg, last_month_wage,
        min_wage_applied, cap_applied, cap_base, basis_wage, years_used,
        years_capped, amount, steps, basis, reason}``
        （``basis_wage`` 为实际使用的计算基数，供报告与口径核对用）
    """
    if termination is None:
        raise InputError("经济补偿计算需要 termination 段（解除情形）")
    if facts.terminate_date is None:
        raise InputError("经济补偿计算需要 terminate_date（工作年限终点）")

    decision = determine_formula(termination)
    formula = decision["formula"]

    service_years = service_years_for_compensation(
        facts.hire_date, facts.terminate_date, ruleset
    )

    wages = list(facts.monthly_wages)
    if not wages:
        raise InputError("经济补偿计算需要 monthly_wages（解除前月工资序列）")

    avg = _monthly_average(wages, ruleset)
    min_wage = ruleset.min_wage_monthly()
    min_wage_applied = avg < min_wage
    basis_wage = min_wage if min_wage_applied else avg

    cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
    cap_applied = basis_wage > cap_base
    calc_base = cap_base if cap_applied else basis_wage

    years_used = service_years
    if cap_applied and years_used > ruleset.severance_cap_years():
        years_used = ruleset.severance_cap_years()

    if formula == "none":
        amount = _ZERO
    elif formula == "2N":
        amount = calc_base * years_used * ruleset.compensation_multiple()
    else:
        amount = calc_base * years_used
        if formula == "N+1":
            # 代通知金 = 劳动者上一个月的工资标准（D-30），不受封顶/下限约束
            amount = amount + wages[-1]

    window = int(ruleset.avg_wage_months())
    sample_count = min(len(wages), window)
    steps = _build_steps(
        decision, service_years, avg, sample_count, min_wage_applied, min_wage,
        cap_base, cap_applied, years_used, wages[-1], formula,
    )

    return {
        "formula": formula,
        "ground": decision["ground"],
        "service_years": service_years,
        "monthly_wage_avg": quantize_money(avg),
        "last_month_wage": quantize_money(wages[-1]),
        "min_wage_applied": min_wage_applied,
        "cap_applied": cap_applied,
        "cap_base": quantize_money(cap_base),
        "basis_wage": quantize_money(calc_base),
        "years_used": years_used,
        "years_capped": years_used,
        "amount": quantize_money(amount),
        "steps": steps,
        "basis": list(decision["basis"]),
        "reason": decision["reason"],
    }


def _build_steps(decision, service_years, avg, sample_count, min_wage_applied, min_wage,
                 cap_base, cap_applied, years_used, last_month_wage, formula):
    # type: (dict, object, object, int, bool, object, object, bool, object, object, str) -> list
    """计算过程留痕（报告「逐项计算过程」用；数值均为运行时动态值）。"""
    steps = ["口径判定：{}".format(decision["reason"])]
    steps.append("工作年限取整：{} 年".format(service_years))
    steps.append("月工资口径：解除前 {} 个月平均应得工资 = {}".format(
        sample_count, quantize_money(avg)))
    if min_wage_applied:
        steps.append("最低工资下限生效：取 {} 元".format(min_wage))
    if cap_applied:
        steps.append("三倍封顶生效：基数取 {} 元（社平工资 × 倍数）".format(
            quantize_money(cap_base)))
        steps.append("封顶时年限不超过上限：年限取 {} 年".format(years_used))
    if formula == "none":
        steps.append("该情形无需支付经济补偿 → 金额 0")
    elif formula == "2N":
        steps.append("违法解除赔偿金 = 基数 × 年限 × 赔偿金倍数")
    elif formula == "N+1":
        steps.append("经济补偿 = 基数 × 年限；代通知金 = 上一个月工资 {}".format(
            quantize_money(last_month_wage)))
    else:
        steps.append("经济补偿 = 基数 × 年限")
    return steps


__all__ = [
    "MILESTONE",
    "FORMULA_BY_GROUND",
    "FORMULA_CLAUSE_IDS",
    "determine_formula",
    "service_years_for_compensation",
    "compute",
]
