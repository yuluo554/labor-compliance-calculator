# -*- coding: utf-8 -*-
"""输入事实模型与校验（plan/04 §2）。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from lcc import decimalutil
from lcc.errors import InputError
from lcc.model import CaseInput, EmploymentFacts, TerminationFacts

BASE = {
    "region_code": "310000",
    "year": 2026,
    "hire_date": "2020-03-01",
    "terminate_date": "2026-06-30",
    "monthly_wages": ["12000.00"] * 12,
    "work_system": "standard",
}


def test_employment_parses_and_decimals():
    facts = EmploymentFacts.from_dict(BASE)
    assert facts.hire_date.year == 2020
    assert facts.terminate_date.year == 2026
    assert isinstance(facts.monthly_wages[0], Decimal)
    assert facts.monthly_wages[0] == Decimal("12000.00")


def test_missing_region_code_raises():
    payload = dict(BASE)
    payload.pop("region_code")
    with pytest.raises(InputError):
        EmploymentFacts.from_dict(payload)


def test_missing_year_raises():
    payload = dict(BASE)
    payload.pop("year")
    with pytest.raises(InputError):
        EmploymentFacts.from_dict(payload)


def test_reversed_dates_raise():
    payload = dict(BASE)
    payload["terminate_date"] = "2019-01-01"
    with pytest.raises(InputError) as exc:
        EmploymentFacts.from_dict(payload)
    assert "倒置" in str(exc.value)


def test_negative_wage_raises():
    payload = dict(BASE)
    payload["monthly_wages"] = ["-1"]
    with pytest.raises(InputError):
        EmploymentFacts.from_dict(payload)


def test_bad_work_system_raises():
    payload = dict(BASE)
    payload["work_system"] = "flexible"
    with pytest.raises(InputError) as exc:
        EmploymentFacts.from_dict(payload)
    assert "work_system" in str(exc.value)


def test_bad_date_format_raises():
    payload = dict(BASE)
    payload["hire_date"] = "2020/3/1 00:00"
    with pytest.raises(InputError):
        EmploymentFacts.from_dict(payload)


def test_termination_ground_enum():
    assert TerminationFacts.from_dict({"ground": "mutual_agreement"}).ground == "mutual_agreement"
    with pytest.raises(InputError) as exc:
        TerminationFacts.from_dict({"ground": "fire_him"})
    assert "ground" in str(exc.value)


def test_case_input_requires_employment():
    with pytest.raises(InputError):
        CaseInput.from_dict({"termination": {"ground": "mutual_agreement"}})


def test_overtime_entries_parse():
    payload = dict(BASE)
    payload["overtime"] = [
        {"date": "2026-05-01", "hours": "8"},
        {"date": "2026-05-10", "hours": "3", "kind": "rest_day"},
    ]
    facts = EmploymentFacts.from_dict(payload)
    assert len(facts.overtime) == 2
    assert facts.overtime[0].kind == "auto"
    assert facts.overtime[1].hours == Decimal("3")


def test_overtime_negative_hours_raise():
    payload = dict(BASE)
    payload["overtime"] = [{"date": "2026-05-01", "hours": "-1"}]
    with pytest.raises(InputError):
        EmploymentFacts.from_dict(payload)


# ---- Decimal 口径（NFR-3） -------------------------------------------------

def test_float_goes_through_str_not_binary():
    value = decimalutil.to_decimal(0.1)
    assert value == Decimal("0.1")
    assert str(value) == "0.1"


def test_bool_is_not_a_number():
    with pytest.raises(TypeError):
        decimalutil.to_decimal(True)


def test_money_quantize_half_up():
    assert decimalutil.money_str(Decimal("1.005")) == "1.01"
    assert decimalutil.money_str(Decimal("1.004")) == "1.00"
    assert decimalutil.money_str(Decimal("2.675")) == "2.68"


def test_json_load_uses_decimal(tmp_path):
    path = tmp_path / "x.json"
    path.write_text('{"a": 0.1, "b": 12345.678}', encoding="utf-8")
    payload = decimalutil.load_json_decimal(str(path))
    assert isinstance(payload["a"], Decimal)
    assert payload["a"] == Decimal("0.1")
    assert payload["b"] == Decimal("12345.678")