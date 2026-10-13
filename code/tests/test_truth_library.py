# -*- coding: utf-8 -*-
"""真值库守门（M1-5 / M1-7）：可复现、可对账、不含真实数据。

这些测试把「冻结产物 + 真值语义单一实现源」变成可执行断言（plan/05 §1.4、§四）：
  * 再生成**逐字节一致**（固定 splitmix64 种子，禁 stdlib random）；
  * 真值可由 :mod:`lcc.benchmark.cases` **独立重算**并逐字段对上（防手改真值）；
  * 每条 ``input_facts`` 都能被 :class:`lcc.model.CaseInput` 接受（防"文档说能跑但喂不进"）；
  * 只使用已核对坐标；假身份；无 CR、以 LF 结尾。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal

import pytest

from lcc.benchmark import cases as truth
from lcc.benchmark.rng import SplitMix64
from lcc.gate import effective_ruleset
from lcc.model import CaseInput
from lcc.params import load_constants, load_ruleset

PROFILES = ("pilot", "boundary")
VERIFIED_COORDINATES = {("110000", 2025), ("110000", 2026), ("310000", 2025), ("310000", 2026)}


def _load_truth(data_dir, profile):
    # type: (str, str) -> dict
    path = os.path.join(data_dir, "truth", "cases-{}.json".format(profile))
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def _all_cases(data_dir):
    # type: (str) -> list
    out = []
    for profile in PROFILES:
        out.extend(_load_truth(data_dir, profile)["cases"])
    return out


def _ruleset_for(region, year, data_dir):
    # type: (str, int, str) -> object
    ruleset = load_ruleset(region, year, data_dir=data_dir)
    constants = load_constants(data_dir=data_dir)
    return effective_ruleset(ruleset, constants, data_dir=data_dir)


# ---- M1-7：再生成逐字节一致 ------------------------------------------------

def test_truth_library_regenerates_byte_identical(repo_root):
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "tools", "gen_cases.py"), "--check"],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "FROZEN_TRUTH_OK" in output


def test_truth_json_has_no_cr_and_ends_with_lf(data_dir):
    for profile in PROFILES:
        path = os.path.join(data_dir, "truth", "cases-{}.json".format(profile))
        with open(path, "rb") as handle:
            blob = handle.read()
        assert b"\r" not in blob, "真值库出现 CR: {}".format(path)
        assert blob.endswith(b"\n"), "真值库应以 LF 结尾: {}".format(path)


def test_generator_does_not_use_stdlib_random(repo_root):
    """守门：生成器与真值语义层不得引入 stdlib ``random``（跨版本不可复现）。"""
    offenders = []
    for rel in ("tools/gen_cases.py",
                os.path.join("code", "src", "lcc", "benchmark", "cases.py"),
                os.path.join("code", "src", "lcc", "benchmark", "rng.py")):
        with open(os.path.join(repo_root, rel), "r", encoding="utf-8") as handle:
            text = handle.read()
        if "import random" in text or "from random" in text:
            offenders.append(rel)
    assert not offenders, "出现 stdlib random: {}".format(offenders)


# ---- splitmix64 参考序列（防"自研 RNG 悄悄漂移"） ---------------------------

def test_splitmix64_matches_reference_sequence():
    rng = SplitMix64(0)
    got = [rng.next_u64() for _ in range(4)]
    assert [hex(value) for value in got] == [
        "0xe220a8397b1dcdaf",
        "0x6e789e6aa1b965f4",
        "0x6c45d188009454f",
        "0xf88bb8a8724c81ec",
    ]


def test_splitmix64_is_deterministic_and_bounded():
    a = [SplitMix64(7).next_below(100) for _ in range(1)]
    b = [SplitMix64(7).next_below(100) for _ in range(1)]
    assert a == b
    rng = SplitMix64(123)
    for _ in range(200):
        value = rng.next_below(10)
        assert 0 <= value < 10


# ---- 真值可独立重算（防手改真值凑引擎） ------------------------------------

def test_stored_truth_recomputes_from_single_source(data_dir):
    """把每条 ``input_facts`` 重新喂进 cases.evaluate，与库中真值逐字段比对。"""
    problems = []
    for case in _all_cases(data_dir):
        region, year = case["coordinate"]
        ruleset = _ruleset_for(str(region), int(year), data_dir)
        parsed = CaseInput.from_dict(case["input_facts"])
        spec = truth.evaluate(parsed, truth.MODULES, ruleset)
        for name, block in spec["modules"].items():
            stored = case["expected"][name]
            recomputed = {
                field: (truth.canonical(field, value) if field != "entries"
                        else [{k: truth.canonical(k, item[k]) for k in item} for item in value])
                for field, value in block["expected"].items()
            }
            if stored != recomputed:
                problems.append((case["case_id"], name, stored, recomputed))
        if case["also_expect"] != {n: list(b["also_expect"]) for n, b in spec["modules"].items()}:
            problems.append((case["case_id"], "also_expect", case["also_expect"], "不一致"))
    assert not problems, "真值与单一实现源不一致（疑似手改）: {}".format(problems[:3])


def test_compare_reports_mismatch_on_tampered_value(data_dir):
    """阳性对照：把真值改坏后 compare 必须报不一致（否则对账是空验的）。"""
    case = _all_cases(data_dir)[0]
    region, year = case["coordinate"]
    ruleset = _ruleset_for(str(region), int(year), data_dir)
    parsed = CaseInput.from_dict(case["input_facts"])
    spec = truth.evaluate(parsed, truth.MODULES, ruleset)

    actual = {}
    for name, block in spec["modules"].items():
        payload = dict(block["expected"])
        actual[name] = payload
    # 先确认未篡改时全通过
    assert truth.compare(parsed, spec, actual, ruleset) == []

    # 篡改一个金额字段
    for name in actual:
        if "amount" in actual[name]:
            actual[name]["amount"] = Decimal(actual[name]["amount"]) + Decimal(1)
            break
    mismatches = truth.compare(parsed, spec, actual, ruleset)
    assert mismatches, "篡改金额后 compare 未报不一致"


# ---- 输入可被模型接受（D-18：文档说的输入必须真能跑） ----------------------

def test_every_case_input_facts_parse(data_dir):
    """每条 ``input_facts`` 都能被模型接受（D-18：文档说的输入必须真能跑）。

    断言带上 case_id —— 失败时直接定位到具体记录，而非只报"某条不合法"。
    """
    for case in _all_cases(data_dir):
        try:
            parsed = CaseInput.from_dict(case["input_facts"])
        except Exception as exc:  # noqa: BLE001 - 需带 case_id 上报
            raise AssertionError(
                "{}: input_facts 无法解析: {}".format(case["case_id"], exc)
            )
        assert parsed.employment.region_code, case["case_id"]
        assert parsed.employment.monthly_wages, case["case_id"]
        assert parsed.termination is not None, case["case_id"]


def test_truth_cases_use_only_verified_coordinates(data_dir):
    for case in _all_cases(data_dir):
        coordinate = (str(case["coordinate"][0]), int(case["coordinate"][1]))
        assert coordinate in VERIFIED_COORDINATES, "真值库含未核对坐标: {}".format(coordinate)


# ---- 合成数据纪律（data/README §四） ---------------------------------------

def test_truth_cases_have_fictional_identities(data_dir):
    for case in _all_cases(data_dir):
        fictional = case.get("fictional") or {}
        assert "示例" in fictional.get("employee_name", ""), case["case_id"]
        assert "示例" in fictional.get("employer_name", ""), case["case_id"]


def test_truth_cases_carry_dimensions_and_also_expect(data_dir):
    for case in _all_cases(data_dir):
        assert case["dimensions"], case["case_id"]
        assert case["also_expect"], case["case_id"]
        # 每条隐含结论必须已登记谓词（否则对账时静默跳过）
        for name, implications in case["also_expect"].items():
            for implication in implications:
                assert implication in truth.IMPLICATIONS, (case["case_id"], implication)


# ---- 覆盖矩阵（plan/05 §1.4） ----------------------------------------------

def test_coverage_matrix_covers_required_dimensions(data_dir):
    cases = _all_cases(data_dir)
    grounds = {case["ground"] for case in cases}
    assert len(grounds) >= 8, "口径判定情形覆盖不足: {}".format(sorted(grounds))

    cap_bands = {case["dimensions"]["cap_band"] for case in cases}
    for band in ("cap_minus_cent", "cap_at", "cap_plus_cent"):
        assert band in cap_bands, "缺封顶边界档: {}".format(band)

    service_months = {case["dimensions"]["service_months"] for case in cases}
    for months in (5, 6, 11, 12, 144, 150):
        assert months in service_months, "缺年限边界: {}".format(months)

    tiers = {case["dimensions"]["service_tier_years"] for case in cases}
    for tier in ("1", "10", "20"):
        assert tier in tiers, "缺年休假分档边界: {}".format(tier)

    systems = {case["dimensions"]["work_system"] for case in cases}
    assert systems == {"standard", "comprehensive", "irregular"}

    assert any(case["dimensions"]["contract_signed"] is False for case in cases)


# ---- 与数据联动：封顶切换点由参数包算出（零字面量） ------------------------

def test_cap_switch_point_is_exact_from_params(data_dir):
    """基数恰好 = 社平×3 时不封顶；+0.01 时封顶。端点由参数包算出，非硬编码。"""
    for region, year in (("110000", 2025), ("310000", 2026)):
        cases = {c["case_id"]: c for c in _all_cases(data_dir)}
        at = cases["boundary-{}-{}-cap-cap_at".format(region, year)]["expected"]["severance"]
        plus = cases["boundary-{}-{}-cap-cap_plus_cent".format(region, year)]["expected"]["severance"]
        assert at["cap_applied"] is False, (region, year, at)
        assert plus["cap_applied"] is True, (region, year, plus)
        assert Decimal(at["monthly_wage_avg"]) == Decimal(at["cap_base"])
