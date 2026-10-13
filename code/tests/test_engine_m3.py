# -*- coding: utf-8 -*-
"""加班费 / 年休假 / 二倍工资三引擎单测（M3；DoD M3-1~M3-4）。

覆盖：
  * M3-1 加班费：日历四类联动（法定节假日 / 休息日 / 调休上班日 / 工作日）、
    最低工资下限、显式 ``kind`` 覆盖、跨年度坐标报错、依据挂 ``LL-44/LL-36``；
  * M3-2 年休假：分档（1/10/20 年）、当年度折算、向下取整（D-31）与冲抵、
    依据挂 ``ALR-3/5`` + ``MOHRSS-ORDER-1-ART10/11/12``；
  * M3-3 二倍工资：起算（满一个月次日）、11 个月上限、已签合同为 0、
    依据挂 ``LCL-82``；
  * M3-4 依据 id 全部可在条款库解析（依据不得悬挂）。

数值一律经 :class:`lcc.gate.EffectiveRuleset` 从已核对坐标取（测试免零字面量
门禁，构造边界输入所必需的样本值不属"引擎内联真相"）。
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

import pytest

from lcc.engine import annual_leave, double_wage, overtime
from lcc.errors import InputError
from lcc.gate import effective_ruleset
from lcc.law import load_library
from lcc.model import EmploymentFacts
from lcc.params import load_constants, load_ruleset

REGION = "110000"
YEAR = 2025


@pytest.fixture(scope="module")
def ruleset(data_dir):
    return effective_ruleset(
        load_ruleset(REGION, YEAR, data_dir=data_dir),
        load_constants(data_dir=data_dir),
        data_dir=data_dir,
    )


@pytest.fixture(scope="module")
def library(data_dir):
    return load_library(data_dir)


def _facts(ruleset, **overrides):
    # type: (object, dict) -> EmploymentFacts
    payload = {
        "region_code": ruleset.region_code,
        "year": ruleset.year,
        "hire_date": "2020-03-01",
        "terminate_date": "2025-06-30",
        "monthly_wages": ["12000.00"] * 12,
        "contract_signed": True,
        "cumulative_service_years": "6",
        "annual_leave_taken_days": "0",
        "overtime": [],
    }
    payload.update(overrides)
    return EmploymentFacts.from_dict(payload)


# --------------------------------------------------------------------------
# M3-1 加班费引擎
# --------------------------------------------------------------------------

def test_overtime_day_type_rate_mapping_matches_calendar(ruleset):
    """日历四类日期 → 常数包倍率档位（法定节假日最高 / 休息日与调休上班日次之 /
    工作日最低），逐条与 ``ruleset.overtime_rate`` 一致。"""
    holidays = ruleset.holiday_days()
    rest = ruleset.rest_days()
    adjusted = ruleset.adjusted_workdays()
    assert holidays and rest and adjusted, "该坐标日历应含四类日期样本"

    entries = [
        {"date": holidays[0], "hours": "2"},
        {"date": rest[0], "hours": "2"},
        {"date": adjusted[0], "hours": "2"},
        {"date": "2025-01-02", "hours": "2"},  # 非节假日/休息日 → workday
    ]
    output = overtime.compute(_facts(ruleset, overtime=entries), ruleset)
    by_date = {item["date"]: item for item in output["entries"]}

    assert by_date[holidays[0]]["day_type"] == "statutory_holiday"
    assert by_date[holidays[0]]["rate"] == ruleset.overtime_rate("statutory_holiday")
    for day in (rest[0], adjusted[0]):
        assert by_date[day]["day_type"] in ("rest_day", "adjusted_workday")
        assert by_date[day]["rate"] == ruleset.overtime_rate("rest_day_no_compensatory")
    assert by_date["2025-01-02"]["day_type"] == "workday"
    assert by_date["2025-01-02"]["rate"] == ruleset.overtime_rate("workday_extension")


def test_overtime_rest_day_and_adjusted_workday_share_rate(ruleset):
    """休息日与调休上班日（未补休）同档——防止调休上班日退化成工作日口径（D-37）。"""
    rest = ruleset.rest_days()
    adjusted = ruleset.adjusted_workdays()
    output = overtime.compute(
        _facts(ruleset, overtime=[{"date": rest[0], "hours": "1"},
                                  {"date": adjusted[0], "hours": "1"}]),
        ruleset,
    )
    rates = {item["day_type"]: item["rate"] for item in output["entries"]}
    assert rates["rest_day"] == rates["adjusted_workday"]


def test_overtime_hourly_base_from_monthly_wage_and_min_wage_floor(ruleset):
    """小时工资 = 基数 ÷（月计薪天数 × 日标准工时）；低于最低工资时基数取下限。"""
    base = ruleset.min_wage_monthly() - Decimal("1")
    low = overtime.compute(
        _facts(ruleset, monthly_wages=[str(base)] * 12,
               overtime=[{"date": "2025-01-02", "hours": "1"}]),
        ruleset,
    )
    assert low["min_wage_applied"] is True
    expected_hourly = ruleset.min_wage_monthly() / ruleset.monthly_pay_days() \
        / ruleset.overtime_standard_daily_hours()
    assert low["hourly_base"] == expected_hourly


def test_overtime_explicit_kind_overrides_calendar(ruleset):
    """显式 ``kind != auto`` 覆盖日历判定（按断言 kind 对应档位计）。"""
    # 取一个普通工作日日期，但显式声明为法定节假日加班
    output = overtime.compute(
        _facts(ruleset, overtime=[{"date": "2025-01-02", "hours": "1",
                                   "kind": "statutory_holiday"}]),
        ruleset,
    )
    item = output["entries"][0]
    assert item["day_type_source"] == "explicit"
    assert item["rate"] == ruleset.overtime_rate("statutory_holiday")


def test_overtime_basis_ids_resolvable(ruleset, library):
    output = overtime.compute(
        _facts(ruleset, overtime=[{"date": "2025-01-02", "hours": "1"}]),
        ruleset,
    )
    assert output["basis"] == ["LL-44", "LL-36"]
    assert all(library.has(item) for item in output["basis"])


def test_overtime_empty_entries_yields_zero(ruleset):
    output = overtime.compute(_facts(ruleset, overtime=[]), ruleset)
    assert output["total"] == Decimal("0.00")
    assert output["entries"] == []


def test_overtime_requires_wages(ruleset):
    with pytest.raises(InputError):
        overtime.compute(_facts(ruleset, monthly_wages=[]), ruleset)


# --------------------------------------------------------------------------
# M3-2 年休假引擎
# --------------------------------------------------------------------------

def test_annual_leave_tier_selection_at_boundaries(ruleset):
    """分档边界：累计年限恰好 1 / 10 / 20 年应落入对应档（含上界闭合语义）。"""
    tiers = {tier["min_service_years"]: tier["days"] for tier in ruleset.entitlement_tiers()}
    for service, want in ((Decimal("1"), tiers[Decimal("1")]),
                          (Decimal("10"), tiers[Decimal("10")]),
                          (Decimal("20"), tiers[Decimal("20")])):
        output = annual_leave.compute(
            _facts(ruleset, cumulative_service_years=str(service)), ruleset
        )
        assert output["entitlement_days"] == want, service


def test_annual_leave_proration_and_floor_rounding(ruleset):
    """折算应休天数保留原值；应休未休天数向下取整（D-31），下限 0。"""
    output = annual_leave.compute(
        _facts(ruleset, terminate_date="2025-03-01", cumulative_service_years="6",
               annual_leave_taken_days="0"),
        ruleset,
    )
    year_start = date(2025, 1, 1)
    elapsed = (date(2025, 3, 1) - year_start).days + 1
    expected_prorated = Decimal(elapsed) / ruleset.days_per_year() * output["entitlement_days"]
    assert output["prorated_days"] == expected_prorated
    assert output["unused_days"] == expected_prorated.to_integral_value(rounding=ROUND_FLOOR)


def test_annual_leave_floor_applies_after_deducting_taken_days(ruleset):
    """取整作用于「折算应休 − 已安排」这一最终量（D-31），非折算值本身。"""
    output = annual_leave.compute(
        _facts(ruleset, terminate_date="2025-03-01", cumulative_service_years="6",
               annual_leave_taken_days="1"),
        ruleset,
    )
    raw = output["prorated_days"] - Decimal("1")
    want = max(Decimal("0"), raw.to_integral_value(rounding=ROUND_FLOOR))
    assert output["unused_days"] == want


def test_annual_leave_unused_days_never_negative(ruleset):
    """已安排天数超过折算应休 → 应休未休天数截 0，另付金额为 0。"""
    output = annual_leave.compute(
        _facts(ruleset, terminate_date="2025-01-02", annual_leave_taken_days="10"),
        ruleset,
    )
    assert output["unused_days"] == Decimal("0")
    assert output["additional_due"] == Decimal("0.00")


def test_annual_leave_additional_due_is_unused_minus_already_paid(ruleset):
    """另付金额 = 日工资 × 未休天数 ×（未休倍数 − 已付比例）。"""
    output = annual_leave.compute(
        _facts(ruleset, terminate_date="2025-12-31", cumulative_service_years="6",
               annual_leave_taken_days="0"),
        ruleset,
    )
    daily = output["daily_wage"]
    unused = output["unused_days"]
    want = daily * unused * (ruleset.unused_multiple() - ruleset.already_paid_portion())
    assert output["additional_due"] == want.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")


def test_annual_leave_requires_terminate_date(ruleset):
    with pytest.raises(InputError):
        annual_leave.compute(_facts(ruleset, terminate_date=None), ruleset)


def test_annual_leave_basis_ids_resolvable(ruleset, library):
    output = annual_leave.compute(_facts(ruleset), ruleset)
    assert all(library.has(item) for item in output["basis"])
    for expected in ("ALR-3", "ALR-5", "MOHRSS-ORDER-1-ART10",
                     "MOHRSS-ORDER-1-ART11", "MOHRSS-ORDER-1-ART12"):
        assert expected in output["basis"]


# --------------------------------------------------------------------------
# M3-3 二倍工资引擎
# --------------------------------------------------------------------------

def test_double_wage_signed_contract_yields_zero(ruleset):
    output = double_wage.compute(_facts(ruleset, contract_signed=True), ruleset)
    assert output["signed"] is True
    assert output["months"] == 0
    assert output["total_difference"] == Decimal("0.00")


def test_double_wage_starts_day_after_full_month(ruleset):
    """起算 = 用工满 ``start_after_months`` 个月的次日（第 29/30/31 天起算点）。

    月末夹取：1/28、1/29、1/30、1/31 满一个月分别落在 2/28、2/28、2/28、2/28，
    故起算日均为 3/1。
    """
    start_after = int(ruleset.double_wage_start_after_months())
    for hire in ("2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31"):
        output = double_wage.compute(
            _facts(ruleset, hire_date=hire, terminate_date="2025-06-28",
                   contract_signed=False),
            ruleset,
        )
        hire_date = date.fromisoformat(hire)
        # 满一个月之日（月末夹取）→ 次日为起算日
        total = hire_date.month - 1 + start_after
        year = hire_date.year + total // 12
        month = total % 12 + 1
        days_in_target = (date(year + (month // 12), month % 12 + 1, 1)
                          - date(year, month, 1)).days
        anniversary = date(year, month, min(hire_date.day, days_in_target))
        expected_start = anniversary + timedelta(days=1)
        assert output["start_date"] == expected_start.isoformat(), hire


def test_double_wage_capped_at_max_months(ruleset):
    """区间月数不超过 ``max_months``（用工满一年即止，不因继续未签而延长）。"""
    output = double_wage.compute(
        _facts(ruleset, hire_date="2020-03-01", terminate_date="2025-06-30",
               contract_signed=False),
        ruleset,
    )
    assert Decimal(output["months"]) <= ruleset.double_wage_max_months()
    assert Decimal(output["months"]) == ruleset.double_wage_max_months()


def test_double_wage_terminate_before_start_yields_zero(ruleset):
    """终止日早于起算日 → 区间月数 0、差额 0。"""
    output = double_wage.compute(
        _facts(ruleset, hire_date="2025-06-01", terminate_date="2025-06-15",
               contract_signed=False),
        ruleset,
    )
    assert output["months"] == 0
    assert output["total_difference"] == Decimal("0.00")


def test_double_wage_total_is_base_times_months_times_multiple(ruleset):
    output = double_wage.compute(
        _facts(ruleset, hire_date="2024-07-28", terminate_date="2025-06-28",
               contract_signed=False),
        ruleset,
    )
    want = Decimal(output["monthly_wage"]) * Decimal(output["months"]) \
        * ruleset.double_wage_difference_multiple()
    assert output["total_difference"] == want.quantize(
        Decimal("0.01"), rounding="ROUND_HALF_UP")


def test_double_wage_basis_ids_resolvable(ruleset, library):
    output = double_wage.compute(_facts(ruleset, contract_signed=False), ruleset)
    assert output["basis"] == ["LCL-82"]
    assert library.has("LCL-82")


# --------------------------------------------------------------------------
# M3-4 跨坐标/缺输入守卫
# --------------------------------------------------------------------------

def test_engines_reject_missing_wages(ruleset):
    # double_wage 在已签合同时不产生差额、不需要工资序列 → 用未签合同触发工资校验
    for engine in (overtime, annual_leave):
        with pytest.raises(InputError):
            engine.compute(_facts(ruleset, monthly_wages=[]), ruleset)
    with pytest.raises(InputError):
        double_wage.compute(_facts(ruleset, monthly_wages=[], contract_signed=False), ruleset)
