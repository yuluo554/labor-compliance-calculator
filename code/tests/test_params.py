# -*- coding: utf-8 -*-
"""参数库：坐标精确匹配、schema 校验、来源纪律（FR-1.1~1.5）。"""

from __future__ import annotations

import json
import os

import pytest

from lcc import params
from lcc.errors import ParamCoordinateError, ParamSchemaError


# ---- 坐标 ----------------------------------------------------------------

def test_load_ruleset_exact_coordinate(data_dir):
    ruleset = params.load_ruleset("310000", 2026, data_dir=data_dir)
    assert ruleset.region_code == "310000"
    assert ruleset.year == 2026
    assert ruleset.coordinate == ("310000", 2026)


def test_unknown_coordinate_raises(data_dir):
    with pytest.raises(ParamCoordinateError) as exc:
        params.load_ruleset("999999", 2026, data_dir=data_dir)
    assert "999999" in str(exc.value)


def test_unknown_year_raises(data_dir):
    """跨年度混用：不存在的年度不得回退到其他年度。"""
    with pytest.raises(ParamCoordinateError):
        params.load_ruleset("310000", 2019, data_dir=data_dir)


def test_no_fuzzy_fallback(data_dir):
    """地区码必须是完整匹配，不做前缀/模糊匹配。"""
    with pytest.raises(ParamCoordinateError):
        params.load_ruleset("31000", 2026, data_dir=data_dir)


def test_list_ruleset_files(data_dir):
    files = params.list_ruleset_files(data_dir)
    names = [os.path.basename(item) for item in files]
    assert "ruleset-310000-2026.json" in names
    assert names == sorted(names)


# ---- schema 校验 ---------------------------------------------------------

def test_validate_rejects_filename_coordinate_mismatch(tmp_path):
    """文件名 ↔ 内部坐标不一致必须报错（FR-1.4 的机制保障）。"""
    rules_dir = tmp_path / "data" / "rules"
    rules_dir.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "region_code": "310000",
        "region_name": "上海市",
        "year": 2026,
        "status": "pending",
        "params": {
            "social_avg_wage_monthly": {"value": "0.00", "status": "pending"},
            "min_wage_monthly": {"value": "0.00", "status": "pending"},
            "holiday_calendar": {"days": [], "status": "pending"},
        },
    }
    # 文件名写 110000，内部写 310000 → 必须被拒
    path = rules_dir / "ruleset-110000-2026.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ParamSchemaError) as exc:
        params.load_ruleset("110000", 2026, data_dir=str(tmp_path / "data"))
    assert "不一致" in str(exc.value)


def test_validate_rejects_verified_without_source(tmp_path):
    """verified 条目缺来源 → 拒绝（FR-1.3）。"""
    rules_dir = tmp_path / "data" / "rules"
    rules_dir.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "region_code": "310000",
        "region_name": "上海市",
        "year": 2026,
        "status": "verified",
        "params": {
            "social_avg_wage_monthly": {"value": "0.00", "status": "verified"},
            "min_wage_monthly": {"value": "0.00", "status": "pending"},
            "holiday_calendar": {"days": [], "status": "pending"},
        },
    }
    (rules_dir / "ruleset-310000-2026.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ParamSchemaError) as exc:
        params.load_ruleset("310000", 2026, data_dir=str(tmp_path / "data"))
    assert "来源" in str(exc.value)


def test_validate_rejects_bad_status(tmp_path):
    rules_dir = tmp_path / "data" / "rules"
    rules_dir.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "region_code": "310000",
        "region_name": "上海市",
        "year": 2026,
        "params": {
            "social_avg_wage_monthly": {"value": "0.00", "status": "whatever"},
            "min_wage_monthly": {"value": "0.00", "status": "pending"},
            "holiday_calendar": {"days": [], "status": "pending"},
        },
    }
    (rules_dir / "ruleset-310000-2026.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ParamSchemaError) as exc:
        params.load_ruleset("310000", 2026, data_dir=str(tmp_path / "data"))
    assert "status" in str(exc.value)


def test_all_repo_rulesets_pass_schema(data_dir):
    """仓库内全部规则包骨架必须通过 schema 校验（坐标/文件名一致）。"""
    files = params.list_ruleset_files(data_dir)
    assert files, "规则包骨架缺失（应先跑 tools/gen_rulesets.py）"
    for path in files:
        match = params.RULES_FILENAME_RE.match(os.path.basename(path))
        ruleset = params.load_ruleset(
            match.group("region"), match.group("year"), data_dir=data_dir
        )
        assert ruleset.region_code == match.group("region")
        assert ruleset.year == int(match.group("year"))


# ---- 常数包 / 地区 -------------------------------------------------------

def test_constants_entries_are_flat_and_complete(data_dir):
    constants = params.load_constants(data_dir)
    paths = set(constants.entries())
    for required in (
        "severance.cap_multiple_of_social_avg",
        "severance.cap_years",
        "severance.rounding.full_year_threshold_months",
        "severance.avg_wage_months",
        "overtime.rates.workday_extension",
        "overtime.rates.rest_day_no_compensatory",
        "overtime.rates.statutory_holiday",
        "annual_leave.monthly_pay_days",
        "annual_leave.unused_multiple",
        "annual_leave.already_paid_portion",
        "annual_leave.days_per_year",
        "annual_leave.entitlement_tiers[0]",
        "annual_leave.entitlement_tiers[2]",
        "double_wage.start_after_months",
        "double_wage.max_months",
    ):
        assert required in paths, required


def test_constants_verified_requires_basis_and_channel(tmp_path):
    (tmp_path / "rules").mkdir()
    path = tmp_path / "constants"
    path.mkdir()
    payload = {
        "schema_version": 1,
        "constants": {
            "severance": {
                "cap_years": {"value": 12, "status": "verified"}
            }
        },
    }
    (path / "statutory-constants.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ParamSchemaError) as exc:
        params.load_constants(data_dir=str(tmp_path))
    assert "basis" in str(exc.value)


def test_regions_require_caliber(data_dir):
    regions = params.load_regions(data_dir)
    assert regions.codes()
    for item in regions.regions:
        assert item.get("avg_wage_caliber"), "口径登记为必填（D-04）"


def test_regions_get_unknown_raises(data_dir):
    regions = params.load_regions(data_dir)
    with pytest.raises(ParamCoordinateError):
        regions.get("000000")


def test_summarize_shape(data_dir):
    summary = params.summarize(data_dir)
    assert summary["rulesets"]
    assert summary["constants_status"] in ("pending", "verified")
    assert summary["regions"]