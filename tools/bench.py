#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内置基准（plan/05 §二）：B1 口径判定 / B2 全模块对账 / B3 参数库自洽 /
B4 参数推导边界扫描 / B5 双向对账（公式推导 vs 穷举恢复）。

设计（plan/05 §2.1、§2.2）：
  * B1 口径判定 —— 解除情形 → N/N+1/2N/none 枚举（含易混边界），目标 100%；
  * B2 全模块对账 —— 真值库全量经四引擎重算后逐字段 + 隐含结论对账 0 mismatch；
  * B3 参数库自洽 —— 非法组合拦截率（不存在坐标、跨坐标混用、pending 条目）；
  * B4 参数推导边界扫描（M4）—— **不依赖真值库样本**：全部切换端点由参数包推出，
    在切换点 ±0.01（金额精度）邻域断言封顶/下限切换，并覆盖年限取整、12 年上限、
    年休假分档、加班三档倍率、二倍工资区间；
  * B5 双向对账（M4）—— **公式推导**的端点与**穷举扫描恢复**的切换点两条独立路径
    互验（封顶切换点、年限取整切换点、12 年上限、年休假分档边界、加班倍率映射、
    二倍工资区间）。

纪律：
  * 全离线、零网络、零 API；全量单次 < 1 秒；
  * 数值一律经 :class:`lcc.gate.EffectiveRuleset` 从数据包取（本脚本零政策字面量）；
  * 指标（通过数/总数、拦截率）由本脚本产出，写入 README 评测表。

用法：
    py -X utf8 tools/bench.py                 # 跑全部基准，达标 exit 0 / 未达标 exit 1
    py -X utf8 tools/bench.py --json          # 以 JSON 输出指标（写 README 用）
    py -X utf8 tools/bench.py --only B4       # 只跑指定基准（B1/B2/B3/B4/B5/positive）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

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
from lcc.engine import annual_leave, double_wage, overtime, severance
from lcc.errors import LccError
from lcc.gate import effective_ruleset
from lcc.model import (
    CaseInput,
    EmploymentFacts,
    TERMINATION_GROUNDS,
    TerminationFacts,
)
from lcc.params import load_constants, load_ruleset

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA_DIR = os.path.join(ROOT, "data")
PROFILES = ("pilot", "boundary")

# 已核对坐标（与 data/README 台账一致）——B4/B5 的扫描面
VERIFIED_COORDINATES = (("110000", 2025), ("110000", 2026), ("310000", 2025), ("310000", 2026))

# 金额精度（1 分）——±0.01 邻域用；属精度约定，非政策数值
_CENT = Decimal("0.01")

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
# 扫描样本构造（仅用于生成输入；政策判定一律由引擎/参数产出）
# --------------------------------------------------------------------------

def _days_in_month(year, month):
    # type: (int, int) -> int
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _add_months(day, months):
    # type: (date, int) -> date
    """加 ``months`` 个日历月（月末夹取）。

    本函数**只用于生成扫描样本日期**；政策结论（年限/天数/倍率）一律由引擎输出或
    参数包推出，不在此处判定——避免基准成为"第二份真相"。
    """
    total = day.month - 1 + int(months)
    year = day.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(day.day, _days_in_month(year, month)))


def _employment(region, year, hire, terminate, wage, **extra):
    # type: (str, int, date, object, object, dict) -> EmploymentFacts
    """构造雇佣事实样本：12 个月等值工资（均值 = ``wage``，避免量化抖动）。"""
    payload = {
        "region_code": str(region),
        "year": int(year),
        "hire_date": hire.isoformat(),
        "terminate_date": terminate.isoformat() if terminate is not None else None,
        "monthly_wages": [str(wage)] * 12,
    }
    payload.update(extra)
    return EmploymentFacts.from_dict(payload)


def _termination(ground, notified=None):
    # type: (str, object) -> TerminationFacts
    return TerminationFacts.from_dict(
        {"ground": ground, "notified_30d_in_advance": notified}
    )


def _workday_sample(ruleset):
    # type: (object) -> str
    """取该坐标日历中一个既非节假日/休息日/调休上班日的普通工作日。"""
    excluded = set(ruleset.holiday_days()) | set(ruleset.rest_days()) \
        | set(ruleset.adjusted_workdays())
    day = date(ruleset.year, 1, 1)
    for _offset in range(366):
        iso = day.isoformat()
        if iso not in excluded and day.weekday() < 5:
            return iso
        day = day + timedelta(days=1)
    raise LccError("未找到普通工作日样本（{}）".format(ruleset.coordinate))


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
# B2 全模块对账（真值库全量 × 四引擎）
# --------------------------------------------------------------------------

def _engine_output(case, parsed, ruleset, module):
    # type: (dict, object, object, str) -> object
    """按模块调用引擎（severance 需 termination；其余三引擎只需 employment）。"""
    if module == "severance":
        return severance.compute(parsed.employment, parsed.termination, ruleset)
    if module == "overtime":
        return overtime.compute(parsed.employment, ruleset)
    if module == "annual_leave":
        return annual_leave.compute(parsed.employment, ruleset)
    if module == "double_wage":
        return double_wage.compute(parsed.employment, ruleset)
    raise LccError("未知计算模块 {!r}".format(module))


def run_b2():
    # type: () -> dict
    """真值库全量记录经四引擎重算后对账（含 cap_band 恰好 ±0.01、年限取整、
    12 年上限、日历四类倍率、年休假分档与向下取整、二倍工资起算与 11 个月上限）。"""
    get_ruleset = _ruleset_cache()
    total = 0
    passed = 0
    failures = []
    for profile in PROFILES:
        for case in _load_cases(profile):
            region, year = case["coordinate"]
            ruleset = get_ruleset(region, year)
            parsed = CaseInput.from_dict(case["input_facts"])
            spec = truth.evaluate(parsed, truth.MODULES, ruleset)
            actual = {
                name: _engine_output(case, parsed, ruleset, name)
                for name in truth.MODULES
            }
            mismatches = truth.compare(parsed, spec, actual, ruleset)
            total += 1
            if not mismatches:
                passed += 1
            else:
                failures.append((case["case_id"], mismatches[:3]))
    return {
        "name": "B2 边界与全模块对账",
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
# B4 参数推导边界扫描（±0.01 邻域；不依赖真值库样本）
# --------------------------------------------------------------------------

def run_b4():
    # type: () -> dict
    """从**规则表/常数包**推导全部有限切换点，在 ±0.01 邻域断言切换语义。

    与 B2 的区别：B2 是"真值库记录重算对账"（样本驱动）；B4 是"参数推导边界"
    （规则驱动）——不依赖真值库是否恰好覆盖某端点。
    """
    get_ruleset = _ruleset_cache()
    checks = []

    def check(label, ok, detail=""):
        checks.append((label, bool(ok), detail))

    for region, year in VERIFIED_COORDINATES:
        ruleset = get_ruleset(region, year)
        tag = "{}/{}".format(region, year)
        cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
        min_wage = ruleset.min_wage_monthly()
        hire = date(2015, 1, 1)
        terminate = date(2025, 6, 30)
        mutual = _termination("mutual_agreement")
        below_cap = cap_base * 8 // 10

        # 1) 三倍封顶切换点 ±0.01（严格大于：恰好等于封顶基数时不封顶）
        for offset, want in ((-_CENT, False), (Decimal(0), False), (_CENT, True)):
            output = severance.compute(
                _employment(region, year, hire, terminate, cap_base + offset), mutual, ruleset
            )
            check("{} 封顶切换 {:+.2f}（cap_base={}）".format(tag, offset, cap_base),
                  output["cap_applied"] is want)

        # 2) 最低工资下限切换点 ±0.01（严格小于：恰好等于下限不触发）
        for offset, want in ((-_CENT, True), (Decimal(0), False), (_CENT, False)):
            output = severance.compute(
                _employment(region, year, hire, terminate, min_wage + offset), mutual, ruleset
            )
            check("{} 最低工资下限 {:+.2f}（min_wage={}）".format(tag, offset, min_wage),
                  output["min_wage_applied"] is want)

        # 3) 年限取整切换点：满 full_year_threshold_months 个月不满 1 年 → 按 1 年
        threshold = int(ruleset.full_year_threshold_months())
        base_hire = date(2024, 1, 1)
        before = severance.compute(
            _employment(region, year, base_hire, _add_months(base_hire, threshold - 1), below_cap),
            mutual, ruleset,
        )
        at = severance.compute(
            _employment(region, year, base_hire, _add_months(base_hire, threshold), below_cap),
            mutual, ruleset,
        )
        check("{} 年限 {} 个月（不满阈值）→ 半个月".format(tag, threshold - 1),
              before["service_years"] == ruleset.round_down_to_half_month())
        check("{} 年限 {} 个月（达阈值）→ 一年".format(tag, threshold),
              at["service_years"] == ruleset.round_up_to_year())

        # 4) 余日折算切换点：余日 14 天不计 / 15 天计半个月（既定口径 D-34）
        anniversary = _add_months(base_hire, 12)
        r14 = severance.compute(
            _employment(region, year, base_hire, anniversary + timedelta(days=14), below_cap),
            mutual, ruleset,
        )
        r15 = severance.compute(
            _employment(region, year, base_hire, anniversary + timedelta(days=15), below_cap),
            mutual, ruleset,
        )
        check("{} 余日 14 天不计月".format(tag),
              r14["service_years"] == Decimal(1))
        check("{} 余日 15 天计半个月".format(tag),
              r15["service_years"] == Decimal(1) + ruleset.round_down_to_half_month())

        # 5) 12 年上限切换点：封顶时年限不超过 cap_years；未及上限不截断
        cap_years = ruleset.severance_cap_years()
        long_out = severance.compute(
            _employment(region, year, date(2005, 1, 1), terminate, cap_base + _CENT),
            mutual, ruleset,
        )
        check("{} 12 年上限生效（service_years > cap_years）".format(tag),
              long_out["service_years"] > cap_years and long_out["years_used"] == cap_years)
        short_out = severance.compute(
            _employment(region, year, date(2019, 1, 1), terminate, cap_base + _CENT),
            mutual, ruleset,
        )
        check("{} 未及上限不截断".format(tag),
              short_out["years_used"] == short_out["service_years"])

        # 6) 加班三档倍率：日历四类 → 常数包三档（法定节假日最高/休息日次之/工作日最低）
        holidays = ruleset.holiday_days()
        rest = ruleset.rest_days()
        adjusted = ruleset.adjusted_workdays()
        entries = [
            {"date": holidays[0], "hours": "1"},
            {"date": rest[0], "hours": "1"},
            {"date": adjusted[0], "hours": "1"},
            {"date": _workday_sample(ruleset), "hours": "1"},
        ]
        ot = overtime.compute(
            _employment(region, year, hire, terminate, below_cap, overtime=entries), ruleset
        )
        rate_by_type = {item["day_type"]: item["rate"] for item in ot["entries"]}
        check("{} 法定节假日倍率".format(tag),
              rate_by_type.get("statutory_holiday") == ruleset.overtime_rate("statutory_holiday"))
        check("{} 休息日倍率".format(tag),
              rate_by_type.get("rest_day") == ruleset.overtime_rate("rest_day_no_compensatory"))
        check("{} 调休上班日倍率".format(tag),
              rate_by_type.get("adjusted_workday") == ruleset.overtime_rate("rest_day_no_compensatory"))
        check("{} 工作日倍率".format(tag),
              rate_by_type.get("workday") == ruleset.overtime_rate("workday_extension"))

        # 7) 年休假分档边界：下界闭合、上界开；累计不满最低档 → 0 天（D-42）
        tiers = ruleset.entitlement_tiers()
        eps = Decimal("0.0001")
        days_by_min = {tier["min_service_years"]: tier["days"] for tier in tiers}
        lowest = min(days_by_min)
        below_all = annual_leave.compute(
            _employment(region, year, hire, terminate, below_cap,
                        cumulative_service_years=str(lowest - eps)),
            ruleset,
        )
        check("{} 年休假 累计不满最低档 → 0 天".format(tag),
              below_all["entitlement_days"] == Decimal(0))
        for tier in tiers:
            low = tier["min_service_years"]
            high = tier["max_service_years_exclusive"]
            at_low = annual_leave.compute(
                _employment(region, year, hire, terminate, below_cap,
                            cumulative_service_years=str(low)),
                ruleset,
            )
            check("{} 年休假 {} 年档下界闭合".format(tag, low),
                  at_low["entitlement_days"] == tier["days"])
            if high is not None:
                below_high = annual_leave.compute(
                    _employment(region, year, hire, terminate, below_cap,
                                cumulative_service_years=str(high - eps)),
                    ruleset,
                )
                at_high = annual_leave.compute(
                    _employment(region, year, hire, terminate, below_cap,
                                cumulative_service_years=str(high)),
                    ruleset,
                )
                check("{} 年休假 {} 年档上界开".format(tag, high),
                      below_high["entitlement_days"] == tier["days"]
                      and at_high["entitlement_days"] == days_by_min[high])

        # 8) 二倍工资：起算日 = 满 start_after_months 个月的次日；区间上限 = max_months
        start_after = int(ruleset.double_wage_start_after_months())
        dw_hire = date(2024, 1, 1)
        dw = double_wage.compute(
            _employment(region, year, dw_hire, None, below_cap, contract_signed=False), ruleset
        )
        check("{} 二倍工资起算日（满 {} 个月次日）".format(tag, start_after),
              dw["start_date"] == (_add_months(dw_hire, start_after) + timedelta(days=1)).isoformat())
        check("{} 二倍工资上限（{} 个月）".format(tag, ruleset.double_wage_max_months()),
              Decimal(dw["months"]) == ruleset.double_wage_max_months())

    total = len(checks)
    passed = sum(1 for _label, ok, _detail in checks if ok)
    failures = ["{} {}".format(label, detail).strip() for label, ok, detail in checks if not ok]
    return {
        "name": "B4 参数推导边界扫描",
        "passed": passed,
        "total": total,
        "target": "全通过",
        "rate": (passed / total) if total else 0.0,
        "ok": passed == total,
        "failures": failures,
    }


# --------------------------------------------------------------------------
# B5 双向对账（公式推导 vs 穷举恢复）
# --------------------------------------------------------------------------

def run_b5():
    # type: () -> dict
    """同一切换点的**两条独立路径**互验（plan/05 §2.2）：

      * 公式推导 —— 由参数包/常数包直接算出的端点（规则驱动）；
      * 穷举恢复 —— 对输入做扫描、由**引擎输出**恢复的切换点（行为驱动）。

    两路径一致 ⇒ 引擎实际行为与其应当遵循的参数语义在端点处吻合；任一侧偏移都会
    被本基准捕获。每条恢复断言均同时验证"确实观察到了切换"（非空验）。
    """
    get_ruleset = _ruleset_cache()
    checks = []

    def check(label, ok, detail=""):
        checks.append((label, bool(ok), detail))

    for region, year in VERIFIED_COORDINATES:
        ruleset = get_ruleset(region, year)
        tag = "{}/{}".format(region, year)
        cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
        below_cap = cap_base * 8 // 10
        mutual = _termination("mutual_agreement")

        # 1) 封顶切换点：公式端点（封顶基数 + 1 分） vs 穷举恢复（逐分扫描）
        formula_switch = cap_base + _CENT
        recovered_switch = None
        wage = cap_base - _CENT * 3
        while wage <= cap_base + _CENT * 3:
            output = severance.compute(
                _employment(region, year, date(2015, 1, 1), date(2025, 6, 30), wage),
                mutual, ruleset,
            )
            if output["cap_applied"]:
                recovered_switch = wage
                break
            wage += _CENT
        check("{} 封顶切换点双向一致".format(tag), recovered_switch == formula_switch,
              "公式={} 穷举={}".format(formula_switch, recovered_switch))

        # 2) 年限取整切换点：公式（满 threshold 个月） vs 穷举（逐月扫描首个达一年）
        threshold = int(ruleset.full_year_threshold_months())
        base_hire = date(2024, 1, 1)
        recovered_month = None
        for index in range(1, threshold + 3):
            output = severance.compute(
                _employment(region, year, base_hire, _add_months(base_hire, index), below_cap),
                mutual, ruleset,
            )
            if output["service_years"] >= ruleset.round_up_to_year():
                recovered_month = index
                break
        check("{} 年限取整切换点双向一致".format(tag), recovered_month == threshold,
              "公式={} 穷举={}".format(threshold, recovered_month))
        half = severance.compute(
            _employment(region, year, base_hire, _add_months(base_hire, threshold - 1), below_cap),
            mutual, ruleset,
        )
        check("{} 不满阈值穷举恢复半个月".format(tag),
              half["service_years"] == ruleset.round_down_to_half_month())

        # 3) 12 年上限：公式（cap_years） vs 穷举（扫描恢复的最大 years_used）
        cap_years = ruleset.severance_cap_years()
        recovered_max = Decimal(0)
        for months in (60, 120, 138, 144, 150, 180, 240):
            output = severance.compute(
                _employment(region, year, _add_months(date(2025, 6, 30), -months),
                            date(2025, 6, 30), cap_base + _CENT),
                mutual, ruleset,
            )
            if output["years_used"] > recovered_max:
                recovered_max = output["years_used"]
        check("{} 12 年上限双向一致".format(tag), recovered_max == cap_years,
              "公式={} 穷举={}".format(cap_years, recovered_max))

        # 4) 年休假分档边界：公式（各档下界） vs 穷举（细步扫描恢复的切换点）
        tiers = ruleset.entitlement_tiers()
        formula_boundaries = [tier["min_service_years"] for tier in tiers
                              if tier["min_service_years"] > 0]
        step = Decimal("0.05")
        ceiling = max(tier["min_service_years"] for tier in tiers) + Decimal(1)
        service = Decimal(0)
        previous = None
        recovered_boundaries = []
        while service <= ceiling:
            output = annual_leave.compute(
                _employment(region, year, date(2015, 1, 1), date(2025, 6, 30), below_cap,
                            cumulative_service_years=str(service)),
                ruleset,
            )
            days = output["entitlement_days"]
            if previous is not None and days != previous:
                recovered_boundaries.append(service)
            previous = days
            service += step
        check("{} 年休假分档边界双向一致".format(tag),
              recovered_boundaries == formula_boundaries,
              "公式={} 穷举={}".format(formula_boundaries, recovered_boundaries))

        # 5) 加班倍率映射：公式（常数包三档） vs 穷举（引擎逐类输出恢复）
        samples = [
            ("statutory_holiday", ruleset.holiday_days()[0]),
            ("rest_day", ruleset.rest_days()[0]),
            ("adjusted_workday", ruleset.adjusted_workdays()[0]),
            ("workday", _workday_sample(ruleset)),
        ]
        formula_rates = {
            "statutory_holiday": ruleset.overtime_rate("statutory_holiday"),
            "rest_day": ruleset.overtime_rate("rest_day_no_compensatory"),
            "adjusted_workday": ruleset.overtime_rate("rest_day_no_compensatory"),
            "workday": ruleset.overtime_rate("workday_extension"),
        }
        output = overtime.compute(
            _employment(region, year, date(2015, 1, 1), date(2025, 6, 30), below_cap,
                        overtime=[{"date": day, "hours": "1"} for _type, day in samples]),
            ruleset,
        )
        recovered_rates = {item["date"]: item["rate"] for item in output["entries"]}
        check("{} 加班倍率映射双向一致".format(tag),
              all(recovered_rates.get(day) == formula_rates[day_type]
                  for day_type, day in samples))
        check("{} 三档倍率互异".format(tag),
              len({formula_rates["statutory_holiday"], formula_rates["rest_day"],
                   formula_rates["workday"]}) == 3)

        # 6) 二倍工资区间：公式（起算日/上限） vs 穷举（逐月扫描恢复月数集合）
        start_after = int(ruleset.double_wage_start_after_months())
        max_months = int(ruleset.double_wage_max_months())
        dw_hire = date(2024, 1, 1)
        recovered_months = set()
        recovered_start = None
        for index in range(0, start_after + max_months + 4):
            output = double_wage.compute(
                _employment(region, year, dw_hire, _add_months(dw_hire, index), below_cap,
                            contract_signed=False),
                ruleset,
            )
            recovered_months.add(output["months"])
            if recovered_start is None:
                recovered_start = output["start_date"]
        formula_start = (_add_months(dw_hire, start_after) + timedelta(days=1)).isoformat()
        check("{} 二倍工资起算日双向一致".format(tag), recovered_start == formula_start,
              "公式={} 穷举={}".format(formula_start, recovered_start))
        check("{} 二倍工资上限双向一致".format(tag), max(recovered_months) == max_months,
              "公式={} 穷举={}".format(max_months, max(recovered_months)))
        check("{} 二倍工资区间穷举覆盖 0..{} 个月".format(tag, max_months),
              recovered_months == set(range(0, max_months + 1)))

    total = len(checks)
    passed = sum(1 for _label, ok, _detail in checks if ok)
    failures = ["{} {}".format(label, detail).strip() for label, ok, detail in checks if not ok]
    return {
        "name": "B5 双向对账（公式推导 vs 穷举恢复）",
        "passed": passed,
        "total": total,
        "target": "全通过",
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


# 基准注册表（``--only`` 按键选择；无 ``--only`` 时跑全部）
_BENCHMARK_KEYS = {
    "B1": run_b1,
    "B2": run_b2,
    "B3": run_b3,
    "B4": run_b4,
    "B5": run_b5,
    "positive": run_positive_control,
}

BENCHMARKS = tuple(_BENCHMARK_KEYS.values())


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="内置基准（B1/B2/B3/B4/B5）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出指标")
    parser.add_argument("--only", default=None, metavar="NAME",
                        help="只跑指定基准（{}）".format("/".join(_BENCHMARK_KEYS)))
    args = parser.parse_args(argv)

    if args.only is not None and args.only not in _BENCHMARK_KEYS:
        sys.stderr.write(
            "用法错误：未知基准名 {!r}；可选: {}\n".format(args.only, "/".join(_BENCHMARK_KEYS))
        )
        return EXIT_USAGE

    selected = BENCHMARKS if args.only is None else (_BENCHMARK_KEYS[args.only],)
    results = [bench() for bench in selected]
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
