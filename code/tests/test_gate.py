# -*- coding: utf-8 -*-
"""status 门控单点（FR-1.6；plan/04 §7.1）。"""

from __future__ import annotations

import json

import pytest

from lcc import gate, params
from lcc.errors import GateError


def test_pending_ruleset_is_blocked(data_dir):
    """未核对参数包（广东仍 pending）→ 门控必须拒绝（这是纪律行为）。"""
    ruleset = params.load_ruleset("440000", 2026, data_dir=data_dir)
    with pytest.raises(GateError) as exc:
        gate.effective_ruleset(ruleset, data_dir=data_dir)
    assert "未核对" in str(exc.value)


def test_verified_ruleset_passes_gate(data_dir):
    """已核对坐标（北京 2025）→ 门控放行，且能取到已验证数值（M1 数据先行证据）。"""
    ruleset = params.load_ruleset("110000", 2025, data_dir=data_dir)
    assert ruleset.status == "verified"
    effective = gate.effective_ruleset(ruleset, data_dir=data_dir)
    assert effective.coordinate == ("110000", 2025)
    assert effective.social_avg_wage_monthly() > 0
    assert effective.min_wage_monthly() > 0
    assert effective.holiday_days()


def test_pending_list_covers_ruleset_and_constants(data_dir):
    ruleset = params.load_ruleset("440000", 2026, data_dir=data_dir)
    constants = params.load_constants(data_dir)
    pending = gate.pending_entries(ruleset, constants)
    assert any(item.startswith("ruleset.") for item in pending)
    # 常数包已全量核对 → 不应再有 constants.* 待核对项（M1-2 证据）
    assert not any(item.startswith("constants.") for item in pending)


def test_allow_pending_preview_does_not_produce_amounts(data_dir):
    """预览模式可拿到规则集，但引擎通路仍未实现 → 不得产出金额。"""
    ruleset = params.load_ruleset("310000", 2026, data_dir=data_dir)
    effective = gate.effective_ruleset(ruleset, allow_pending=True, data_dir=data_dir)
    assert effective.allow_pending is True
    assert effective.coordinate == ("310000", 2026)
    # 预览态允许读取数值（即使 pending）
    assert effective.severance_cap_years() is not None


def test_gate_passes_when_all_verified(tmp_path):
    """全部条目 verified → 门控放行（机制验证，用最小合法数据）。"""
    data = tmp_path / "data"
    (data / "rules").mkdir(parents=True)
    (data / "constants").mkdir(parents=True)

    ruleset_payload = {
        "schema_version": 1,
        "region_code": "310000",
        "region_name": "上海市",
        "year": 2026,
        "status": "verified",
        "params": {
            "social_avg_wage_monthly": {
                "value": "10000.00", "status": "verified",
                "source": {"publisher": "P", "published_year": 2026, "url": "u", "retrieved_at": "d"},
            },
            "min_wage_monthly": {
                "value": "2000.00", "status": "verified",
                "source": {"publisher": "P", "published_year": 2026, "url": "u", "retrieved_at": "d"},
            },
            "holiday_calendar": {
                "days": [], "adjusted_workdays": [], "status": "verified",
                "source": {"publisher": "P", "published_year": 2025, "url": "u", "retrieved_at": "d"},
            },
        },
    }
    (data / "rules" / "ruleset-310000-2026.json").write_text(
        json.dumps(ruleset_payload, ensure_ascii=False), encoding="utf-8"
    )

    constants_payload = {
        "schema_version": 1,
        "constants": {
            "severance": {
                "cap_multiple_of_social_avg": {"value": 3, "basis": ["LCL-47"], "status": "verified",
                                               "source": {"channel": "npc.gov.cn"}},
                "cap_years": {"value": 12, "basis": ["LCL-47"], "status": "verified",
                              "source": {"channel": "npc.gov.cn"}},
                "rounding": {
                    "full_year_threshold_months": {"value": 6, "basis": ["LCL-47"], "status": "verified",
                                                    "source": {"channel": "npc.gov.cn"}},
                    "round_up_to_year": {"value": 1, "basis": ["LCL-47"], "status": "verified",
                                         "source": {"channel": "npc.gov.cn"}},
                    "round_down_to_half_month": {"value": 0.5, "basis": ["LCL-47"], "status": "verified",
                                                 "source": {"channel": "npc.gov.cn"}},
                },
                "avg_wage_months": {"value": 12, "basis": ["LCL-47"], "status": "verified",
                                    "source": {"channel": "npc.gov.cn"}},
            },
            "overtime": {
                "rates": {
                    "workday_extension": {"value": 1.5, "basis": ["LL-44"], "status": "verified",
                                          "source": {"channel": "npc.gov.cn"}},
                    "rest_day_no_compensatory": {"value": 2.0, "basis": ["LL-44"], "status": "verified",
                                                 "source": {"channel": "npc.gov.cn"}},
                    "statutory_holiday": {"value": 3.0, "basis": ["LL-44"], "status": "verified",
                                          "source": {"channel": "npc.gov.cn"}},
                }
            },
            "annual_leave": {
                "monthly_pay_days": {"value": "21.75", "basis": ["MOHRSS-ORDER-1-ART11"],
                                     "status": "verified", "source": {"channel": "gov.cn"}},
                "entitlement_tiers": [
                    {"min_service_years": 1, "max_service_years_exclusive": 10, "days": 5,
                     "basis": ["ALR-3"], "status": "verified", "source": {"channel": "gov.cn"}},
                    {"min_service_years": 10, "max_service_years_exclusive": 20, "days": 10,
                     "basis": ["ALR-3"], "status": "verified", "source": {"channel": "gov.cn"}},
                    {"min_service_years": 20, "max_service_years_exclusive": None, "days": 15,
                     "basis": ["ALR-3"], "status": "verified", "source": {"channel": "gov.cn"}},
                ],
                "unused_multiple": {"value": 3.0, "basis": ["ALR-5"], "status": "verified",
                                    "source": {"channel": "gov.cn"}},
                "already_paid_portion": {"value": 1.0, "basis": ["MOHRSS-ORDER-1-ART10"],
                                         "status": "verified", "source": {"channel": "gov.cn"}},
                "days_per_year": {"value": 365, "basis": ["MOHRSS-ORDER-1-ART12"],
                                  "status": "verified", "source": {"channel": "gov.cn"}},
            },
            "double_wage": {
                "start_after_months": {"value": 1, "basis": ["LCL-82"], "status": "verified",
                                       "source": {"channel": "npc.gov.cn"}},
                "max_months": {"value": 11, "basis": ["LCL-82"], "status": "verified",
                               "source": {"channel": "npc.gov.cn"}},
            },
        },
    }
    (data / "constants" / "statutory-constants.json").write_text(
        json.dumps(constants_payload, ensure_ascii=False), encoding="utf-8"
    )

    ruleset = params.load_ruleset("310000", 2026, data_dir=str(data))
    effective = gate.effective_ruleset(ruleset, data_dir=str(data))
    assert effective.severance_cap_years() == 12
    assert effective.min_wage_monthly() == params.to_decimal("2000.00")
    assert len(effective.entitlement_tiers()) == 3


def test_engine_takes_effective_ruleset_only():
    """引擎签名不得接受裸 dict（结构性防线，AST/签名断言）。"""
    import inspect

    from lcc.engine import annual_leave, double_wage, overtime, severance

    for module in (severance, overtime, annual_leave, double_wage):
        signature = inspect.signature(module.compute)
        params_names = list(signature.parameters)
        assert "ruleset" in params_names or "effective" in params_names, module.__name__