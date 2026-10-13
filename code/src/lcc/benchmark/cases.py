"""合成雇佣档案的**真值语义单一实现源**（plan/05 §1.4、§四.1）。

生成器（``tools/gen_cases.py``）、测试与基准（M4）共用本模块：

* 真值（``expected``）与隐含结论（``also_expect``）在此定义一次；
* **不许改真值凑引擎**：引擎与本模块不一致时改引擎 + 加测试，不动本文件凑数；
* 全部法定数值经 :class:`~lcc.gate.EffectiveRuleset` 取数（常数包），本模块
  不含内联政策数值 → 受零政策字面量门禁扫描。

对账语义（plan/05 §四.1）：``expected`` 为**主期望**（逐字段必须相等）；
``also_expect`` 为同一输入**隐含的其余结论**，以 id 形式登记，由
:data:`IMPLICATIONS` 的谓词机械校验——避免"只对上主字段、隐含结论无人管"。

口径出处见 plan/06 决策记录：D-30（代通知金）、D-31（年休假取整）、
D-32（月工资口径）、D-33（加班基数）、D-34（年限余日）。
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from ..decimalutil import quantize_money
from ..model import CaseInput

_ZERO = Decimal(0)
_ONE = Decimal(1)
_HALF = Decimal("0.5")
# 余日折算阈值（天）：余日 ≥ 15 天计 0.5 个月（既定口径 D-34，<100 属通用计算常量）
_REMAINDER_HALF_MONTH_DAYS = 15
# 天数/日工资的记录精度（精度约定，非政策数值）
_DAYS_PLACES = "0.000001"
# N+1 隐含结论校验容差：金额两位量化的一个分位量级（精度约定，非政策数值）
_WAGE_QUANTIZE_TOLERANCE = Decimal("0.10")

MODULES = ("severance", "overtime", "annual_leave", "double_wage")

# 字段 → 呈现量化位数（None/缺省 = 原样）
_FIELD_PLACES = {
    "service_years": "0.5",
    "monthly_wage_avg": "0.01",
    "last_month_wage": "0.01",
    "cap_base": "0.01",
    "years_used": "0.5",
    "amount": "0.01",
    "hourly_base": "0.000001",
    "total": "0.01",
    "entitlement_days": "1",
    "prorated_days": _DAYS_PLACES,
    "daily_wage": _DAYS_PLACES,
    "additional_due": "0.01",
    "monthly_wage": "0.01",
    "total_difference": "0.01",
    "rate": "0.01",
    "hours": "0.01",
    "entry_amount": "0.01",
}


# --------------------------------------------------------------------------
# 通用小工具
# --------------------------------------------------------------------------

def _quantize(value, places):
    # type: (object, str) -> Decimal
    return Decimal(value).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def canonical(field, value):
    # type: (str, object) -> object
    """字段值 → 记录口径（Decimal 量化后转字符串；其余原样）。

    生成器与 :func:`compare` 共用本函数 → 呈现与对账口径只有一份实现。
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        places = _FIELD_PLACES.get(field)
        return str(_quantize(value, places)) if places else str(value)
    if isinstance(value, int):
        return str(value)
    return value


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
    """``(完整月数, 余日)``；``end < start`` 报错。"""
    if end < start:
        raise ValueError("终止日期早于起始日期")
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if _add_months(start, months) > end:
        months -= 1
    anchor = _add_months(start, months)
    return months, (end - anchor).days


def _monthly_average(wages, ruleset):
    # type: (list, object) -> Decimal
    """解除前 ``avg_wage_months`` 个月平均应得工资（不足则按实际月份）。"""
    if not wages:
        raise ValueError("缺少 monthly_wages")
    window = int(ruleset.avg_wage_months())
    sample = wages[-window:] if len(wages) > window else wages
    return sum(sample) / Decimal(len(sample))


# --------------------------------------------------------------------------
# 模块一：经济补偿 / 赔偿金（plan/04 §3）
# --------------------------------------------------------------------------

def _severance_formula(termination):
    # type: (object) -> str
    """解除情形 → 口径（plan/04 §3.1）。纯映射，无政策数值。"""
    ground = termination.ground
    if ground in ("employee_fault_dismissal", "employee_resignation_voluntary"):
        return "none"
    if ground == "illegal_termination":
        return "2N"
    if ground == "employer_unilateral_no_fault" and not termination.notified_30d_in_advance:
        return "N+1"
    return "N"


def service_years_for_compensation(hire_date, terminate_date, ruleset):
    # type: (date, date, object) -> Decimal
    """工作年限取整（plan/04 §3.2 + D-34）：完整月数 + 余日（≥15 天计 0.5 月），
    再按第 47 条取整（满 6 个月不满 1 年按 1 年；不满 6 个月按半个月）。"""
    months, remainder = _months_and_remainder(hire_date, terminate_date)
    service_months = Decimal(months)
    if remainder >= _REMAINDER_HALF_MONTH_DAYS:
        service_months = service_months + _HALF

    full_years = (service_months / 12).to_integral_value(rounding=ROUND_FLOOR)
    rem_months = service_months - full_years * 12
    if rem_months >= ruleset.full_year_threshold_months():
        return full_years + ruleset.round_up_to_year()
    if rem_months > 0:
        return full_years + ruleset.round_down_to_half_month()
    return full_years


def severance_expected(case, ruleset):
    # type: (CaseInput, object) -> tuple
    employment = case.employment
    termination = case.termination
    if termination is None:
        raise ValueError("severance 需要 termination 段")
    if employment.terminate_date is None:
        raise ValueError("severance 需要 terminate_date")

    formula = _severance_formula(termination)
    service_years = service_years_for_compensation(
        employment.hire_date, employment.terminate_date, ruleset
    )

    wages = list(employment.monthly_wages)
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

    expected = {
        "formula": formula,
        "service_years": service_years,
        "monthly_wage_avg": quantize_money(avg),
        "last_month_wage": quantize_money(wages[-1]),
        "min_wage_applied": min_wage_applied,
        "cap_applied": cap_applied,
        "cap_base": quantize_money(cap_base),
        "years_used": years_used,
        "amount": quantize_money(amount),
    }
    also = ["cap_implies_years_within_limit"] if cap_applied else ["no_cap_means_full_years"]
    if min_wage_applied:
        also.append("min_wage_raises_base")
    if formula == "none":
        also.append("none_formula_yields_zero")
    if formula == "N+1":
        also.append("n_plus_1_uses_last_month_wage")
    return expected, also


# --------------------------------------------------------------------------
# 模块二：加班费（plan/04 §4）
# --------------------------------------------------------------------------

def rate_kind_for_day_type(day_type):
    # type: (str) -> str
    """日历日期类型 → 常数包倍率档位（与 engine/overtime.py 同口径）。"""
    if day_type == "statutory_holiday":
        return "statutory_holiday"
    if day_type in ("rest_day", "adjusted_workday"):
        return "rest_day_no_compensatory"
    return "workday_extension"


def overtime_expected(case, ruleset):
    # type: (CaseInput, object) -> tuple
    employment = case.employment
    base = _monthly_average(list(employment.monthly_wages), ruleset)
    min_wage = ruleset.min_wage_monthly()
    if base < min_wage:
        base = min_wage

    hourly = base / ruleset.monthly_pay_days() / ruleset.overtime_standard_daily_hours()

    entries = []
    total = _ZERO
    for item in employment.overtime:
        day = item.date.isoformat()
        day_type = ruleset.holiday_day_type(day)
        rate = ruleset.overtime_rate(rate_kind_for_day_type(day_type))
        amount = hourly * item.hours * rate
        total = total + amount
        entries.append(
            {
                "date": day,
                "day_type": day_type,
                "rate": rate,
                "hours": item.hours,
                "entry_amount": quantize_money(amount),
            }
        )

    expected = {
        "hourly_base": hourly,
        "total": quantize_money(total),
        "entries": entries,
    }
    also = []
    if any(item["day_type"] == "statutory_holiday" for item in entries):
        also.append("statutory_holiday_uses_holiday_rate")
    if any(item["day_type"] in ("rest_day", "adjusted_workday") for item in entries):
        also.append("rest_days_use_rest_rate")
    return expected, also


# --------------------------------------------------------------------------
# 模块三：未休年休假折算（plan/04 §5）
# --------------------------------------------------------------------------

def annual_leave_expected(case, ruleset):
    # type: (CaseInput, object) -> tuple
    employment = case.employment
    terminate_date = employment.terminate_date
    if terminate_date is None:
        raise ValueError("annual_leave 需要 terminate_date")

    service = employment.cumulative_service_years
    entitlement = None
    for tier in ruleset.entitlement_tiers():
        low = tier["min_service_years"]
        high = tier["max_service_years_exclusive"]
        if service >= low and (high is None or service < high):
            entitlement = tier["days"]
            break
    if entitlement is None:
        raise ValueError("累计工作年限 {} 未落入任何年休假分档".format(service))

    elapsed = (terminate_date - date(terminate_date.year, 1, 1)).days + 1
    prorated = Decimal(elapsed) / ruleset.days_per_year() * entitlement

    unused_raw = prorated - employment.annual_leave_taken_days
    # R-02 已闭环（D-31）：不足 1 整天不计 → 向下取整，下限 0
    unused = unused_raw.to_integral_value(rounding=ROUND_FLOOR)
    if unused < _ZERO:
        unused = _ZERO

    monthly = _monthly_average(list(employment.monthly_wages), ruleset)
    daily = monthly / ruleset.monthly_pay_days()

    additional = (
        daily * unused * ruleset.unused_multiple()
        - daily * unused * ruleset.already_paid_portion()
    )

    expected = {
        "entitlement_days": entitlement,
        "prorated_days": prorated,
        "taken_days": employment.annual_leave_taken_days,
        "unused_days": unused,
        "daily_wage": daily,
        "additional_due": quantize_money(additional),
    }
    return expected, ["unused_days_is_integral"]


# --------------------------------------------------------------------------
# 模块四：未签书面劳动合同二倍工资（plan/04 §6）
# --------------------------------------------------------------------------

def double_wage_expected(case, ruleset):
    # type: (CaseInput, object) -> tuple
    employment = case.employment
    if employment.contract_signed:
        return {"signed": True, "months": 0, "total_difference": _ZERO}, []

    hire = employment.hire_date
    start_after = int(ruleset.double_wage_start_after_months())
    max_months = int(ruleset.double_wage_max_months())

    start = _add_months(hire, start_after) + timedelta(days=1)      # 满一个月的次日
    hard_end = _add_months(hire, start_after + max_months)          # 满一年之日（上限）
    end = employment.terminate_date or hard_end
    if end > hard_end:
        end = hard_end

    if end < start:
        months_count = 0
    else:
        months_count = _months_and_remainder(start, end)[0] + 1     # 首尾含当月

    monthly = _monthly_average(list(employment.monthly_wages), ruleset)
    difference = monthly * months_count * ruleset.double_wage_difference_multiple()

    expected = {
        "signed": False,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "months": months_count,
        "monthly_wage": quantize_money(monthly),
        "total_difference": quantize_money(difference),
    }
    return expected, ["double_wage_capped_at_max_months"]


_EVALUATORS = {
    "severance": severance_expected,
    "overtime": overtime_expected,
    "annual_leave": annual_leave_expected,
    "double_wage": double_wage_expected,
}


# --------------------------------------------------------------------------
# 隐含结论谓词（also_expect 的机械校验）
# --------------------------------------------------------------------------

def _pred_cap_implies_years_within_limit(actual, ruleset):
    return bool(actual.get("cap_applied")) and \
        Decimal(actual.get("years_used")) <= ruleset.severance_cap_years()


def _pred_no_cap_means_full_years(actual, ruleset):
    if actual.get("cap_applied"):
        return True
    return Decimal(actual.get("years_used")) == Decimal(actual.get("service_years"))


def _pred_min_wage_raises_base(actual, ruleset):
    return Decimal(actual.get("monthly_wage_avg")) == ruleset.min_wage_monthly()


def _pred_none_formula_yields_zero(actual, ruleset):
    return Decimal(actual.get("amount")) == _ZERO


def _pred_n_plus_1_uses_last_month_wage(actual, ruleset):
    """N+1 的「+1」是**上一个月工资**（D-30），不是封顶/下限后的基数。

    机械校验：从 ``amount`` 中剥离 N 部分（= 实际计算基数 × 年限）后，余量必须
    等于 ``last_month_wage``。基数优先取引擎报告的 ``basis_wage``，缺失时按口径
    回退（封顶值 / 最低工资 / 月平均工资）；金额两位量化 → 容差取一个分位量级
    （仍能捕获 1 元级篡改）。

    历史注记：M1 原实现为「封顶时上月工资必须 > 封顶基数」，与真值自身
    ``expected.amount`` 矛盾——上月工资恰好等于封顶基数的合法巧合会被误判
    （实测 1 例）；M2 改为下述等价式判定（见 plan/06 D-39）。
    """
    if actual.get("formula") != "N+1":
        return True
    if actual.get("basis_wage") is not None:
        basis = Decimal(actual.get("basis_wage"))
    elif actual.get("cap_applied"):
        basis = Decimal(actual.get("cap_base"))
    elif actual.get("min_wage_applied"):
        basis = ruleset.min_wage_monthly()
    else:
        basis = Decimal(actual.get("monthly_wage_avg"))
    residual = Decimal(actual.get("amount")) - basis * Decimal(actual.get("years_used"))
    return abs(residual - Decimal(actual.get("last_month_wage"))) <= _WAGE_QUANTIZE_TOLERANCE


def _pred_statutory_holiday_uses_holiday_rate(actual, ruleset):
    want = ruleset.overtime_rate("statutory_holiday")
    return all(
        Decimal(item["rate"]) == want
        for item in actual.get("entries") or []
        if item.get("day_type") == "statutory_holiday"
    )


def _pred_rest_days_use_rest_rate(actual, ruleset):
    want = ruleset.overtime_rate("rest_day_no_compensatory")
    return all(
        Decimal(item["rate"]) == want
        for item in actual.get("entries") or []
        if item.get("day_type") in ("rest_day", "adjusted_workday")
    )


def _pred_unused_days_is_integral(actual, ruleset):
    value = Decimal(actual.get("unused_days"))
    return value == value.to_integral_value(rounding=ROUND_FLOOR)


def _pred_double_wage_capped_at_max_months(actual, ruleset):
    return Decimal(actual.get("months")) <= ruleset.double_wage_max_months()


IMPLICATIONS = {
    "cap_implies_years_within_limit": _pred_cap_implies_years_within_limit,
    "no_cap_means_full_years": _pred_no_cap_means_full_years,
    "min_wage_raises_base": _pred_min_wage_raises_base,
    "none_formula_yields_zero": _pred_none_formula_yields_zero,
    "n_plus_1_uses_last_month_wage": _pred_n_plus_1_uses_last_month_wage,
    "statutory_holiday_uses_holiday_rate": _pred_statutory_holiday_uses_holiday_rate,
    "rest_days_use_rest_rate": _pred_rest_days_use_rest_rate,
    "unused_days_is_integral": _pred_unused_days_is_integral,
    "double_wage_capped_at_max_months": _pred_double_wage_capped_at_max_months,
}


# --------------------------------------------------------------------------
# 公开 API
# --------------------------------------------------------------------------

def evaluate(case, modules, ruleset):
    # type: (CaseInput, tuple, object) -> dict
    """产出 ``{"modules": {name: {"expected": ..., "also_expect": [...]}}}``。"""
    payload = {}
    for name in modules:
        if name not in _EVALUATORS:
            raise ValueError("未知计算模块 {!r}".format(name))
        expected, also = _EVALUATORS[name](case, ruleset)
        payload[name] = {"expected": expected, "also_expect": also}
    return {"modules": payload}


def compare(case, spec, actual, ruleset):
    # type: (CaseInput, dict, dict, object) -> list
    """引擎输出 ``actual`` 与真值 ``spec`` 对账；返回不一致条目列表（空 = 全通过）。

    ``actual`` 形如 ``{module: {字段: 值}}``。逐字段比对主期望，并校验
    ``also_expect`` 隐含结论。
    """
    mismatches = []
    for name, block in (spec.get("modules") or {}).items():
        got = (actual or {}).get(name)
        if got is None:
            mismatches.append((name, "<module>", "有结论", "缺失"))
            continue
        for field, want in (block.get("expected") or {}).items():
            if field == "entries":
                mismatches.extend(_compare_entries(name, want, got.get(field) or []))
                continue
            if canonical(field, got.get(field)) != canonical(field, want):
                mismatches.append((name, field, canonical(field, want),
                                   canonical(field, got.get(field))))
        for implication in block.get("also_expect") or []:
            predicate = IMPLICATIONS.get(implication)
            if predicate is None:
                mismatches.append((name, implication, "已登记谓词", "未登记"))
            elif not predicate(got, ruleset):
                mismatches.append((name, implication, "成立", "不成立"))
    return mismatches


def _compare_entries(name, want_entries, have_entries):
    # type: (str, list, list) -> list
    problems = []
    if len(want_entries) != len(have_entries):
        problems.append((name, "entries", "{} 条".format(len(want_entries)),
                         "{} 条".format(len(have_entries))))
        return problems
    for index, (want, have) in enumerate(zip(want_entries, have_entries)):
        for field in ("date", "day_type"):
            if want.get(field) != have.get(field):
                problems.append((name, "entries[{}].{}".format(index, field),
                                 want.get(field), have.get(field)))
        for field in ("rate", "hours", "entry_amount"):
            if canonical(field, want.get(field)) != canonical(field, have.get(field)):
                problems.append((name, "entries[{}].{}".format(index, field),
                                 canonical(field, want.get(field)),
                                 canonical(field, have.get(field))))
    return problems


__all__ = [
    "MODULES",
    "IMPLICATIONS",
    "canonical",
    "evaluate",
    "compare",
    "service_years_for_compensation",
    "rate_kind_for_day_type",
    "severance_expected",
    "overtime_expected",
    "annual_leave_expected",
    "double_wage_expected",
]
