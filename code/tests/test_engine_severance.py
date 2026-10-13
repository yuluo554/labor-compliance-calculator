# -*- coding: utf-8 -*-
"""经济补偿/赔偿金引擎单测（M2；DoD M2-1~M2-5）。

覆盖：
  * M2-1 口径判定 9 种情形（含易混边界：第 40 条未通知 → N+1、第 39 条 → 0、第 38 条 → N）；
  * M2-2 年限取整（5/6/11/12 个月边界）；
  * M2-3 三倍封顶（恰好/±0.01）+ 12 年上限（11.5/12/12.5/13 年）；
  * M2-4 最低工资下限生效；
  * M2-5 结果挂 LCL-46/47/40/48/87 依据，且条款库可解析（依据不得悬挂）。

数值一律经 :class:`lcc.gate.EffectiveRuleset` 从已核对坐标取（测试免零字面量门禁，
构造边界输入所必需的样本值不属"引擎内联真相"）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from lcc.engine import severance
from lcc.errors import ComputationError, InputError
from lcc.gate import effective_ruleset
from lcc.law import load_library
from lcc.model import CaseInput, EmploymentFacts, TerminationFacts
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


def _facts(ruleset, hire, terminate, wages, **overrides):
    # type: (object, str, str, list, dict) -> EmploymentFacts
    payload = {
        "region_code": ruleset.region_code,
        "year": ruleset.year,
        "hire_date": hire,
        "terminate_date": terminate,
        "monthly_wages": [str(value) for value in wages],
        "contract_signed": True,
    }
    payload.update(overrides)
    return EmploymentFacts.from_dict(payload)


def _term(ground, notified=None):
    # type: (str, object) -> TerminationFacts
    return TerminationFacts.from_dict(
        {"ground": ground, "notified_30d_in_advance": notified}
    )


# --------------------------------------------------------------------------
# M2-1 口径判定 9 种情形（基准 B1）
# --------------------------------------------------------------------------

NINE_CASES = (
    ("mutual_agreement", None, "N"),
    ("employee_fault_dismissal", None, "none"),
    ("employer_unilateral_no_fault", True, "N"),
    ("employer_unilateral_no_fault", False, "N+1"),
    ("economic_layoff", None, "N"),
    ("illegal_termination", None, "2N"),
    ("contract_expiry_employer_no_renewal", None, "N"),
    ("employee_resignation_art38", None, "N"),
    ("employee_resignation_voluntary", None, "none"),
)


@pytest.mark.parametrize("ground,notified,expected", NINE_CASES)
def test_determine_formula_nine_cases(ground, notified, expected):
    decision = severance.determine_formula(_term(ground, notified))
    assert decision["formula"] == expected, (ground, notified)
    assert decision["ground"] == ground
    assert decision["reason"]
    assert decision["basis"] == severance.FORMULA_CLAUSE_IDS[expected]


def test_confusable_boundaries():
    """易混边界：第 40 条未提前通知 → N+1（非 2N）；第 39 条 → 0；第 38 条 → N。"""
    assert severance.determine_formula(
        _term("employer_unilateral_no_fault", False))["formula"] == "N+1"
    assert severance.determine_formula(
        _term("employee_fault_dismissal"))["formula"] == "none"
    assert severance.determine_formula(
        _term("employee_resignation_art38"))["formula"] == "N"


def test_determine_formula_rejects_unknown_ground():
    with pytest.raises(InputError):
        severance.determine_formula(_term("no_such_ground"))


def test_all_grounds_have_a_formula():
    from lcc.model import TERMINATION_GROUNDS

    for ground in TERMINATION_GROUNDS:
        assert ground in severance.FORMULA_BY_GROUND, ground


# --------------------------------------------------------------------------
# M2-2 年限取整（5/6/11/12 个月边界）
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "months,expected_years",
    ((5, "0.5"), (6, "1.0"), (11, "1.0"), (12, "1.0")),
)
def test_service_years_rounding(ruleset, months, expected_years):
    terminate = date(YEAR, 6, 28)
    hire = severance._add_months(terminate, -months)
    got = severance.service_years_for_compensation(hire, terminate, ruleset)
    assert got == Decimal(expected_years), (months, got)


def test_service_years_remainder_threshold(ruleset):
    """余日 ≥ 15 天计半个月，否则不计（D-34）。"""
    terminate = date(YEAR, 6, 28)
    anchor = severance._add_months(terminate, -12)
    assert severance.service_years_for_compensation(anchor, terminate, ruleset) == Decimal("1.0")
    assert severance.service_years_for_compensation(
        date(anchor.year, anchor.month, anchor.day - 14), terminate, ruleset) == Decimal("1.0")
    assert severance.service_years_for_compensation(
        date(anchor.year, anchor.month, anchor.day - 15), terminate, ruleset) == Decimal("1.5")


def test_service_years_rejects_inverted_range(ruleset):
    with pytest.raises(ComputationError):
        severance.service_years_for_compensation(
            date(2025, 6, 28), date(2024, 1, 1), ruleset)


# --------------------------------------------------------------------------
# M2-3 三倍封顶（恰好/±0.01）+ 12 年上限
# --------------------------------------------------------------------------

def test_cap_switch_point_is_strict_greater(ruleset):
    """恰好等于封顶基数不封顶；+0.01 才封顶（严格大于）。"""
    cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
    cent = Decimal("0.01")
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", [cap_base] * 12)
    at = severance.compute(facts, _term("mutual_agreement"), ruleset)
    assert at["cap_applied"] is False
    assert at["monthly_wage_avg"] == at["cap_base"] == cap_base.quantize(Decimal("0.01"))

    facts = _facts(ruleset, "2024-06-28", "2025-06-28", [cap_base + cent] * 12)
    plus = severance.compute(facts, _term("mutual_agreement"), ruleset)
    assert plus["cap_applied"] is True

    facts = _facts(ruleset, "2024-06-28", "2025-06-28", [cap_base - cent] * 12)
    minus = severance.compute(facts, _term("mutual_agreement"), ruleset)
    assert minus["cap_applied"] is False


@pytest.mark.parametrize("months,service_years", ((137, "11.5"), (144, "12"), (146, "12.5"),
                                                   (156, "13")))
def test_cap_twelve_year_limit(ruleset, months, service_years):
    """封顶生效时年限 ≤ 12；不封顶时年限按实际（可超 12）。"""
    cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
    terminate = date(YEAR, 6, 28)
    hire = severance._add_months(terminate, -months)

    capped = severance.compute(
        _facts(ruleset, hire.isoformat(), terminate.isoformat(),
               [cap_base + Decimal("0.01")] * 12),
        _term("mutual_agreement"), ruleset)
    assert capped["service_years"] == Decimal(service_years)
    assert capped["years_used"] == min(Decimal(service_years), ruleset.severance_cap_years())

    uncapped = severance.compute(
        _facts(ruleset, hire.isoformat(), terminate.isoformat(),
               [ruleset.min_wage_monthly()] * 12),
        _term("mutual_agreement"), ruleset)
    assert uncapped["cap_applied"] is False
    assert uncapped["years_used"] == Decimal(service_years)


def test_cap_uses_param_driven_base(ruleset):
    """封顶基数由参数包算出（社平 × 倍数），非硬编码。"""
    cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
    facts = _facts(ruleset, "2024-06-28", "2025-06-28",
                   [cap_base + Decimal("1")] * 12)
    out = severance.compute(facts, _term("mutual_agreement"), ruleset)
    assert out["cap_base"] == cap_base.quantize(Decimal("0.01"))


# --------------------------------------------------------------------------
# M2-4 最低工资下限生效
# --------------------------------------------------------------------------

def test_min_wage_floor_applied(ruleset):
    """月工资 < 最低工资 → 取最低工资（仅经济补偿）。"""
    floor = ruleset.min_wage_monthly()
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", [floor - Decimal("1")] * 12)
    out = severance.compute(facts, _term("mutual_agreement"), ruleset)
    assert out["min_wage_applied"] is True
    assert out["basis_wage"] == floor.quantize(Decimal("0.01"))
    assert out["amount"] == (floor * out["years_used"]).quantize(Decimal("0.01"))


def test_min_wage_floor_not_applied_above_floor(ruleset):
    floor = ruleset.min_wage_monthly()
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", [floor + Decimal("1")] * 12)
    out = severance.compute(facts, _term("mutual_agreement"), ruleset)
    assert out["min_wage_applied"] is False


# --------------------------------------------------------------------------
# M2-5 依据条款（LCL-46/47/40/48/87）+ 代通知金口径
# --------------------------------------------------------------------------

def test_basis_ids_are_formula_specific_and_resolvable(data_dir):
    library = load_library(data_dir)
    for formula, ids in severance.FORMULA_CLAUSE_IDS.items():
        for clause_id in ids:
            assert library.has(clause_id), (formula, clause_id)


def test_compute_attaches_basis_for_each_formula(ruleset):
    expected_basis = {
        "N": ["LCL-46", "LCL-47"],
        "N+1": ["LCL-40", "LCL-47"],
        "2N": ["LCL-48", "LCL-87"],
        "none": [],
    }
    grounds = {
        "N": _term("mutual_agreement"),
        "N+1": _term("employer_unilateral_no_fault", False),
        "2N": _term("illegal_termination"),
        "none": _term("employee_resignation_voluntary"),
    }
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", ["12000.00"] * 12)
    for formula, term in grounds.items():
        out = severance.compute(facts, term, ruleset)
        assert out["formula"] == formula
        assert out["basis"] == expected_basis[formula], formula


def test_n_plus_1_adds_last_month_wage_not_capped_base(ruleset):
    """代通知金 = 上一个月工资（D-30），不受封顶/下限约束。"""
    cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
    wages = [cap_base + Decimal("1")] * 11 + [cap_base + Decimal("500")]
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", wages)
    out = severance.compute(facts, _term("employer_unilateral_no_fault", False), ruleset)
    assert out["formula"] == "N+1"
    assert out["cap_applied"] is True
    assert out["last_month_wage"] == (cap_base + Decimal("500")).quantize(Decimal("0.01"))
    n_part = Decimal(out["basis_wage"]) * out["years_used"]
    assert out["amount"] == (n_part + Decimal(out["last_month_wage"])).quantize(Decimal("0.01"))


def test_none_formula_yields_zero(ruleset):
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", ["12000.00"] * 12)
    for ground in ("employee_fault_dismissal", "employee_resignation_voluntary"):
        out = severance.compute(facts, _term(ground), ruleset)
        assert out["formula"] == "none"
        assert out["amount"] == Decimal("0.00")
        assert out["basis"] == []


def test_compute_two_n_uses_compensation_multiple(ruleset):
    """2N = 基数 × 年限 × 赔偿金倍数（倍数取自常数包）。"""
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", ["12000.00"] * 12)
    out = severance.compute(facts, _term("illegal_termination"), ruleset)
    base = Decimal(out["monthly_wage_avg"])
    want = (base * out["years_used"] * ruleset.compensation_multiple()).quantize(Decimal("0.01"))
    assert out["amount"] == want


# --------------------------------------------------------------------------
# 输入守卫
# --------------------------------------------------------------------------

def test_compute_requires_termination(ruleset):
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", ["12000.00"] * 12)
    with pytest.raises(InputError):
        severance.compute(facts, None, ruleset)


def test_compute_requires_terminate_date(ruleset):
    facts = _facts(ruleset, "2024-06-28", None, ["12000.00"] * 12)
    with pytest.raises(InputError):
        severance.compute(facts, _term("mutual_agreement"), ruleset)


def test_compute_requires_wages(ruleset):
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", [])
    with pytest.raises(InputError):
        severance.compute(facts, _term("mutual_agreement"), ruleset)


def test_compute_averages_at_most_avg_wage_months(ruleset):
    """窗口取解除前 ``avg_wage_months`` 个月；更早的月份不参与平均。"""
    window = int(ruleset.avg_wage_months())
    old = [Decimal("1000.00")] * 6
    recent = [Decimal("20000.00")] * window
    facts = _facts(ruleset, "2020-06-28", "2025-06-28", old + recent)
    out = severance.compute(facts, _term("mutual_agreement"), ruleset)
    assert out["monthly_wage_avg"] == Decimal("20000.00")


def test_engine_signature_accepts_only_effective_ruleset(ruleset):
    """引擎取数只经 EffectiveRuleset（结构性防线：传裸 dict 会在取数时报错）。"""
    facts = _facts(ruleset, "2024-06-28", "2025-06-28", ["12000.00"] * 12)
    with pytest.raises((AttributeError, TypeError)):
        severance.compute(facts, _term("mutual_agreement"), {"min_wage_monthly": 1})


def test_case_input_end_to_end(ruleset):
    """经 CaseInput 解析的真实输入结构可直接计算（D-18）。"""
    case = CaseInput.from_dict({
        "employment": {
            "region_code": ruleset.region_code,
            "year": ruleset.year,
            "hire_date": "2020-03-01",
            "terminate_date": "2025-06-30",
            "monthly_wages": ["12000.00"] * 12,
        },
        "termination": {"ground": "mutual_agreement", "notified_30d_in_advance": True},
    })
    out = severance.compute(case.employment, case.termination, ruleset)
    assert out["formula"] == "N"
    assert Decimal(out["amount"]) > 0
    assert out["steps"]
