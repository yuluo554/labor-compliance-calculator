#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置基准（plan/05 §二）：B1 口径判定 / B2 封顶取整边界 / B3 参数库自洽。

设计（plan/05 §2.1、§2.2）：
  * B1 口径判定 —— 解除情形 → N/N+1/2N/none 枚举（含易混边界），目标 100%；
  * B2 封顶与取整边界 —— 真值库中 ``cap_band`` 边界档（恰好 ±0.01）与
    年限取整/12 年上限记录经引擎重算后对账 0 mismatch；
  * B3 参数库自洽 —— 非法组合拦截率（不存在坐标、跨坐标混用、pending 条目）。

纪律：
  * 全离线、零网络、零 API；全量单次 < 1 秒；
  * 数值一律经 :class:`lcc.gate.EffectiveRuleset` 从数据包取（本脚本零政策字面量）；
  * 指标（通过数/总数、拦截率）由本脚本产出，写入 README 评测表。

用法：
    py -X utf8 tools/bench.py            # 跑全部基准，达标 exit 0 / 未达标 exit 1
    py -X utf8 tools/bench.py --json     # 以 JSON 输出指标（写 README 用）
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code", "src"))

try:
    from lcc._stdio import _ensure_utf8_stdio
except ImportError:  # 兜底：脱离仓库布局时仍可运行
    def _ensure_utf8_stdio(stream_names=("stdout", "stderr")):
        # type: (object) -> None
        for name in stream_names:
            stream = getattr(sys, name, None)
            if stream is None:
                continue
            encoding = getattr(stream, "encoding", None) or ""
            try:
                "劳动合规".encode(encoding)
            except (UnicodeEncodeError, LookupError):
                reconfigure = getattr(stream, "reconfigure", None)
                if reconfigure is not None:
                    try:
                        reconfigure(encoding="utf-8")
                    except (ValueError, OSError):
                        pass

from lcc.benchmark import cases as truth
from lcc.engine import severance
from lcc.errors import LccError
from lcc.gate import effective_ruleset
from lcc.model import CaseInput, TERMINATION_GROUNDS, TerminationFacts
from lcc.params import load_constants, load_ruleset

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA_DIR = os.path.join(ROOT, "data")
PROFILES = ("pilot", "boundary")

EXIT_OK = 0
EXIT_BELOW_TARGET = 1
EXIT_USAGE = 2


def _load_cases(profile):
    # type: (str) -> list
    path = os.path.join(DATA_DIR, "truth", "cases-{}.json".format(profile))
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=None)["cases"]


def _ruleset_cache():
    # type: () -> dict
    cache = {}

    def get(region, year):
        key = (str(region), int(year))
        if key not in cache:
            ruleset = load_ruleset(key[0], key[1], data_dir=DATA_DIR)
            constants = load_constants(data_dir=DATA_DIR)
            cache[key] = effective_ruleset(ruleset, constants, data_dir=DATA_DIR)
        return cache[key]

    return get


# --------------------------------------------------------------------------
# B1 口径判定
# --------------------------------------------------------------------------

# 期望口径：与 plan/04 §3.1 映射表一致（纯枚举，无数值政策字面量）
EXPECTED_FORMULA = {
    ("mutual_agreement", None): "N",
    ("employee_fault_dismissal", None): "none",
    ("employer_unilateral_no_fault", True): "N",
    ("employer_unilateral_no_fault", False): "N+1",
    ("economic_layoff", None): "N",
    ("illegal_termination", None): "2N",
    ("contract_expiry_employer_no_renewal", None): "N",
    ("employee_resignation_art38", None): "N",
    ("employee_resignation_voluntary", None): "none",
}


def run_b1():
    # type: () -> dict
    """口径判定 9 种情形枚举（含易混边界）→ 准确率。"""
    total = 0
    passed = 0
    failures = []
    for (ground, notified), want in EXPECTED_FORMULA.items():
        total += 1
        got = severance.determine_formula(
            TerminationFacts.from_dict(
                {"ground": ground, "notified_30d_in_advance": notified}
            )
        )["formula"]
        if got == want:
            passed += 1
        else:
            failures.append((ground, notified, want, got))
    # 覆盖完整性：模型枚举的每一种 ground 都要在基准里出现
    covered = {ground for ground, _notified in EXPECTED_FORMULA}
    for ground in TERMINATION_GROUNDS:
        if ground not in covered:
            total += 1
            failures.append((ground, "<未枚举>", "<有口径>", "缺失"))
    return {
        "name": "B1 口径判定",
        "passed": passed,
        "total": total,
        "target": "100%",
        "rate": (passed / total) if total else 0.0,
        "ok": passed == total,
        "failures": failures,
    }


# --------------------------------------------------------------------------
# B2 封顶与取整边界
# --------------------------------------------------------------------------

def run_b2():
    # type: () -> dict
    """真值库边界记录经引擎重算后对账（含 cap_band 恰好 ±0.01 与年限取整/12 年上限）。"""
    get_ruleset = _ruleset_cache()
    total = 0
    passed = 0
    failures = []
    for profile in PROFILES:
        for case in _load_cases(profile):
            region, year = case["coordinate"]
            ruleset = get_ruleset(region, year)
            parsed = CaseInput.from_dict(case["input_facts"])
            spec = truth.evaluate(parsed, ("severance",), ruleset)
            output = severance.compute(parsed.employment, parsed.termination, ruleset)
            mismatches = truth.compare(parsed, spec, {"severance": output}, ruleset)
            total += 1
            if not mismatches:
                passed += 1
            else:
                failures.append((case["case_id"], mismatches[:3]))
    return {
        "name": "B2 封顶与取整边界",
        "passed": passed,
        "total": total,
        "target": "全通过",
        "rate": (passed / total) if total else 0.0,
        "ok": passed == total,
        "failures": failures,
    }


# --------------------------------------------------------------------------
# B3 参数库自洽（非法组合拦截率）
# --------------------------------------------------------------------------

def run_b3():
    # type: () -> dict
    """非法组合拦截：不存在坐标 / 年度回退 / 跨坐标混用 / pending 条目。

    「拦截」= 抛出 :class:`lcc.errors.LccError`（exit 2 语义），不得静默给出结果。
    """
    checks = []

    def probe(label, fn):
        try:
            fn()
        except LccError:
            checks.append((label, True))
        else:
            checks.append((label, False))

    # 1) 不存在的坐标 → ParamCoordinateError
    probe("不存在坐标 999999/2026",
          lambda: load_ruleset("999999", 2026, data_dir=DATA_DIR))

    # 2) 坐标存在但年度不存在 → 精确匹配、无回退（ParamCoordinateError）
    probe("年度不存在 110000/1999（精确匹配不回退）",
          lambda: load_ruleset("110000", 1999, data_dir=DATA_DIR))

    # 3) pending 规则包坐标（广东）→ 门控拦截
    def _pending_gate():
        ruleset = load_ruleset("440000", 2026, data_dir=DATA_DIR)
        effective_ruleset(ruleset, load_constants(data_dir=DATA_DIR), data_dir=DATA_DIR)
    probe("pending 坐标 440000/2026（门控拦截）", _pending_gate)

    # 4) 跨坐标混用：请求坐标与参数包内部坐标不一致 → ParamSchemaError
    def _cross_coordinate():
        ruleset = load_ruleset("110000", 2026, data_dir=DATA_DIR)
        from lcc.params import validate_ruleset
        validate_ruleset(ruleset, expected_region="110000", expected_year=2025)
    probe("跨坐标混用（2026 包按 2025 校验）", _cross_coordinate)

    # 5) pending 常数条目 → 门控拦截（临时数据目录内翻转一条状态，真实走门控）
    def _pending_constants():
        import shutil
        import tempfile

        from lcc.decimalutil import decimal_default, load_json_decimal
        from lcc.params import STATUS_PENDING

        with tempfile.TemporaryDirectory() as tmp:
            for name in ("constants", "law", "regions", "rules", "truth"):
                src = os.path.join(DATA_DIR, name)
                if os.path.isdir(src):
                    shutil.copytree(src, os.path.join(tmp, name))
            constants_path = os.path.join(tmp, "constants", "statutory-constants.json")
            payload = load_json_decimal(constants_path)
            payload["constants"]["severance"]["cap_years"]["status"] = STATUS_PENDING
            with open(constants_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2,
                          default=decimal_default)
            ruleset = load_ruleset("110000", 2025, data_dir=tmp)
            effective_ruleset(ruleset, load_constants(data_dir=tmp), data_dir=tmp)
    probe("pending 常数条目（门控拦截）", _pending_constants)

    total = len(checks)
    passed = sum(1 for _label, ok in checks if ok)
    failures = [label for label, ok in checks if not ok]
    return {
        "name": "B3 参数库自洽（拦截率）",
        "passed": passed,
        "total": total,
        "target": "100%",
        "rate": (passed / total) if total else 0.0,
        "ok": passed == total,
        "failures": failures,
    }


# --------------------------------------------------------------------------
# 正向对照：已核对坐标必须放行（防"拦截"空验）
# --------------------------------------------------------------------------

def run_positive_control():
    # type: () -> dict
    """阳性对照：已核对坐标（京沪×2025/2026）必须能过门控并算出金额。

    没有这一条，B3 的「拦截率 100%」可能只是因为什么都拦（空验）。
    """
    coordinates = (("110000", 2025), ("110000", 2026), ("310000", 2025), ("310000", 2026))
    total = 0
    passed = 0
    failures = []
    for region, year in coordinates:
        total += 1
        try:
            ruleset = load_ruleset(region, year, data_dir=DATA_DIR)
            constants = load_constants(data_dir=DATA_DIR)
            effective = effective_ruleset(ruleset, constants, data_dir=DATA_DIR)
            facts = CaseInput.from_dict({
                "employment": {
                    "region_code": region,
                    "year": year,
                    "hire_date": "2020-03-01",
                    "terminate_date": "{}-06-30".format(year),
                    "monthly_wages": ["12000.00"] * 12,
                },
                "termination": {"ground": "mutual_agreement"},
            })
            output = severance.compute(facts.employment, facts.termination, effective)
            if output["amount"] is None:
                raise LccError("无金额结论")
            passed += 1
        except LccError as exc:
            failures.append(((region, year), exc.message))
    return {
        "name": "阳性对照（已核对坐标放行）",
        "passed": passed,
        "total": total,
        "target": "全通过",
        "rate": (passed / total) if total else 0.0,
        "ok": passed == total,
        "failures": failures,
    }


BENCHMARKS = (run_b1, run_b2, run_b3, run_positive_control)


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="内置基准（B1/B2/B3）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出指标")
    args = parser.parse_args(argv)

    results = [bench() for bench in BENCHMARKS]
    all_ok = all(item["ok"] for item in results)

    if args.json:
        sys.stdout.write(json.dumps(
            {"benchmarks": results, "ok": all_ok}, ensure_ascii=False, indent=2
        ) + "\n")
    else:
        for item in results:
            mark = "[OK]  " if item["ok"] else "[FAIL]"
            sys.stdout.write("{mark} {name}: {passed}/{total}（目标 {target}）\n".format(
                mark=mark, name=item["name"], passed=item["passed"],
                total=item["total"], target=item["target"]))
            if not item["ok"]:
                for failure in item["failures"][:5]:
                    sys.stdout.write("        {}\n".format(failure))
        sys.stdout.write("\n基准结论：{}\n".format("全部达标" if all_ok else "存在未达标项"))

    return EXIT_OK if all_ok else EXIT_BELOW_TARGET


if __name__ == "__main__":
    sys.exit(main())
