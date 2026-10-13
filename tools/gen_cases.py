#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""合成雇佣档案生成器：产出 ``data/truth/cases-<profile>.json``（M1-5）。

纪律（plan/05 §1.4、§四）：
  * **自研 splitmix64**（:mod:`lcc.benchmark.rng`），禁 stdlib ``random``；
    固定种子 + 显式遍历顺序 → **两次生成逐字节一致**（配守门测试）；
  * 真值由 :mod:`lcc.benchmark.cases` 单一实现源产出（**不许改真值凑引擎**）；
  * 全部法定数值经 :class:`lcc.gate.EffectiveRuleset` 从数据包取（本脚本零政策字面量）；
  * 假身份：姓名「示例员工X」、企业名虚构；**禁止真实劳动者数据**；
  * 确定性落盘：``write_bytes`` + 显式 ``\\n``，产物**不含时间戳**。

用法：
    py -X utf8 tools/gen_cases.py            # 生成全部 profile（幂等覆盖）
    py -X utf8 tools/gen_cases.py --check    # 只校验再生成位级一致
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

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
from lcc.benchmark.rng import SplitMix64
from lcc.gate import effective_ruleset
from lcc.model import CaseInput
from lcc.params import load_constants, load_ruleset

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA_DIR = os.path.join(ROOT, "data")
TRUTH_DIR = os.path.join(DATA_DIR, "truth")

# 固定种子（splitmix64）；profile 间用不同种子避免序列重合
SEEDS = {"pilot": 20261013, "boundary": 20261014}

# 已核对坐标（与 data/README 台账一致）
VERIFIED_COORDINATES = (("110000", 2025), ("110000", 2026), ("310000", 2025), ("310000", 2026))

ALL_GROUNDS = (
    "mutual_agreement",
    "employee_fault_dismissal",
    "employer_unilateral_no_fault",
    "economic_layoff",
    "illegal_termination",
    "contract_expiry_employer_no_renewal",
    "employee_resignation_art38",
    "employee_resignation_voluntary",
)

# 年限维度：月数（含 5/6/11/12 边界与 11.5/12/12.5/13 年封顶维度）
SERVICE_MONTHS = (5, 6, 11, 12, 30, 60, 138, 144, 150, 156)
# 年休假分档维度（累计工作年限）
SERVICE_YEARS_TIERS = ("1", "5", "9.5", "10", "15", "20", "25")
# 封顶维度：相对封顶基数的倍数
CAP_BANDS = ("below", "at", "above")
WORK_SYSTEMS = ("standard", "comprehensive", "irregular")
TERMINATE_DAYS = (15, 28)

_FICTIONAL_NAMES = ("示例员工A", "示例员工B", "示例员工C", "示例员工D")
_FICTIONAL_EMPLOYER = "示例科技有限公司"


def _load_ruleset(region, year):
    # type: (str, int) -> object
    ruleset = load_ruleset(region, year, data_dir=DATA_DIR)
    constants = load_constants(data_dir=DATA_DIR)
    return effective_ruleset(ruleset, constants, data_dir=DATA_DIR)


def _hire_date(terminate, months, remainder_days):
    # type: (date, int, int) -> date
    total = terminate.month - 1 - months
    year = terminate.year + total // 12
    month = total % 12 + 1
    days_in_month = (date(year + (month // 12), month % 12 + 1, 1) - date(year, month, 1)).days
    hire = date(year, month, min(terminate.day, days_in_month))
    return hire - timedelta(days=remainder_days)


def _wage_series(rng, band, cap_base, min_wage):
    # type: (SplitMix64, str, object, object) -> list
    """12 个月工资序列（确定性抖动）。

    ``cap_minus_cent`` / ``cap_at`` / ``cap_plus_cent`` 为**精确边界**（12 个月等值），
    用于断言三倍封顶切换点 ``>`` 的语义（恰好等于封顶基数时不封顶）。
    """
    cent = Decimal("0.01")
    if band == "cap_minus_cent":
        return [str(cap_base - cent) for _ in range(12)]
    if band == "cap_at":
        return [str(cap_base) for _ in range(12)]
    if band == "cap_plus_cent":
        return [str(cap_base + cent) for _ in range(12)]

    if band == "below":
        target = cap_base * 8 // 10
    elif band == "at":
        target = cap_base
    else:
        target = cap_base * 12 // 10
    floor_wage = min_wage * 12 // 10
    if target < floor_wage:
        target = floor_wage

    series = []
    for _index in range(12):
        value = target + rng.next_int(-200, 200)
        if value < min_wage:
            value = min_wage
        series.append(str(value.quantize(cent, rounding=ROUND_HALF_UP)))
    return series


def _overtime_entries(ruleset, rng):
    # type: (object, SplitMix64) -> list
    """从该坐标日历取四类日期各一条（法定节假日/休息日/调休上班日/普通工作日）。"""
    picks = []
    for day_type, want in (
        ("statutory_holiday", ruleset.holiday_days()),
        ("rest_day", ruleset.rest_days()),
        ("adjusted_workday", ruleset.adjusted_workdays()),
    ):
        if want:
            picks.append((want[rng.next_below(len(want))], day_type))
    # 普通工作日：从该年度中挑一个既非节假日也非休息日的日期
    year = ruleset.year
    holidays = set(ruleset.holiday_days()) | set(ruleset.rest_days())
    for offset in range(200):
        candidate = date(year, 1, 1) + timedelta(days=offset)
        iso = candidate.isoformat()
        if iso not in holidays and candidate.weekday() < 5:
            picks.append((iso, "workday"))
            break
    picks.sort(key=lambda item: item[0])
    return [{"date": iso, "hours": str(rng.next_int(1, 8))} for iso, _kind in picks]


def _build_case(case_id, region, year, ground, service_months, remainder_days,
                cap_band, tier_years, work_system, terminate_day, signed, rng):
    # type: (str, str, int, str, int, int, str, str, str, int, bool, SplitMix64) -> dict
    ruleset = _load_ruleset(region, year)
    terminate = date(year, 6, terminate_day)
    hire = _hire_date(terminate, service_months, remainder_days)

    cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
    wages = _wage_series(rng, cap_band, cap_base, ruleset.min_wage_monthly())

    employment = {
        "region_code": region,
        "year": year,
        "hire_date": hire.isoformat(),
        "terminate_date": terminate.isoformat(),
        "monthly_wages": wages,
        "work_system": work_system,
        "cumulative_service_years": tier_years,
        "contract_signed": signed,
        "contract_signed_date": hire.isoformat() if signed else None,
        "annual_leave_taken_days": str(rng.next_int(0, 3)),
        "overtime": _overtime_entries(ruleset, rng),
    }
    termination = {
        "ground": ground,
        "notified_30d_in_advance": (ground != "employer_unilateral_no_fault") or (rng.next_below(2) == 0),
    }
    input_facts = {"employment": employment, "termination": termination}

    case = CaseInput.from_dict(input_facts)
    spec = truth.evaluate(case, truth.MODULES, ruleset)

    expected = {}
    also_expect = {}
    for name, block in spec["modules"].items():
        expected[name] = _canonicalize(block["expected"])
        also_expect[name] = list(block["also_expect"])

    return {
        "case_id": case_id,
        "profile": None,                      # 由调用方填
        "coordinate": [region, year],
        "ground": ground,
        "dimensions": {
            "service_months": service_months,
            "remainder_days": remainder_days,
            "cap_band": cap_band,
            "service_tier_years": tier_years,
            "work_system": work_system,
            "contract_signed": signed,
        },
        "fictional": {"employee_name": _FICTIONAL_NAMES[0], "employer_name": _FICTIONAL_EMPLOYER},
        "input_facts": input_facts,
        "expected": expected,
        "also_expect": also_expect,
    }


def _canonicalize(payload):
    # type: (dict) -> dict
    """把真值字段归到记录口径（Decimal → 量化字符串），共用 cases.canonical。"""
    out = {}
    for field, value in payload.items():
        if field == "entries":
            out[field] = [
                {key: truth.canonical(key, item.get(key)) for key in item}
                for item in value
            ]
        else:
            out[field] = truth.canonical(field, value)
    return out


def _pilot_cases():
    # type: () -> list
    rng = SplitMix64(SEEDS["pilot"])
    out = []
    index = 0
    for region, year in VERIFIED_COORDINATES:
        for ground in ALL_GROUNDS:
            for service_months in SERVICE_MONTHS:
                cap_band = CAP_BANDS[index % len(CAP_BANDS)]
                tier = SERVICE_YEARS_TIERS[index % len(SERVICE_YEARS_TIERS)]
                system = WORK_SYSTEMS[index % len(WORK_SYSTEMS)]
                remainder = (0, 12)[index % 2]
                terminate_day = TERMINATE_DAYS[index % len(TERMINATE_DAYS)]
                signed = (index % 5) != 0
                case_id = "pilot-{}-{}-{:03d}".format(region, year, index)
                out.append(_build_case(
                    case_id, region, year, ground, service_months, remainder,
                    cap_band, tier, system, terminate_day, signed, rng,
                ))
                index += 1
    for item in out:
        item["profile"] = "pilot"
    return out


def _boundary_cases():
    # type: () -> list
    """边界档案：年限 5/6/11/12 个月与 11.5/12/12.5/13 年、封顶恰好 ±0.01、
    年休假分档 1/10/20 年、二倍工资起算与 11 个月上限。"""
    rng = SplitMix64(SEEDS["boundary"])
    out = []
    year_edges = (5, 6, 11, 12, 138, 144, 150, 156)

    # 1) 年限 × 封顶档（带抖动）——ID 含封顶档，避免不同档互相覆盖
    for region, year in VERIFIED_COORDINATES[:2]:
        for months in year_edges:
            for cap_band in CAP_BANDS:
                case_id = "boundary-{}-{}-y{:03d}-{}".format(region, year, months, cap_band)
                out.append(_build_case(
                    case_id, region, year, "employer_unilateral_no_fault",
                    months, 0, cap_band, "12", "standard", 28, True, rng,
                ))

    # 2) 封顶切换点精确断言：基数恰好 = 社平×3 ±0.01（12 个月等值）
    for region, year in VERIFIED_COORDINATES:
        for band in ("cap_minus_cent", "cap_at", "cap_plus_cent"):
            case_id = "boundary-{}-{}-cap-{}".format(region, year, band)
            out.append(_build_case(
                case_id, region, year, "illegal_termination",
                144, 0, band, "12", "standard", 28, True, rng,
            ))

    # 3) 年限余日边界（≥15 天计 0.5 月）：12 个月 + 0/14/15 天（0→1.0 年，15→1.5 年）
    for region, year in VERIFIED_COORDINATES[:2]:
        for remainder in (0, 14, 15):
            case_id = "boundary-{}-{}-rem{:02d}".format(region, year, remainder)
            out.append(_build_case(
                case_id, region, year, "mutual_agreement",
                12, remainder, "below", "5", "standard", 28, True, rng,
            ))

    # 4) 年休假分档边界（累计年限 1 / 10 / 20）
    for region, year in VERIFIED_COORDINATES[:2]:
        for tier in ("1", "10", "20"):
            case_id = "boundary-{}-{}-al{}".format(region, year, tier)
            out.append(_build_case(
                case_id, region, year, "mutual_agreement",
                24, 0, "below", tier, "standard", 15, True, rng,
            ))

    # 5) 二倍工资：未签合同，覆盖起算点（1/2 个月）与 11 个月上限
    for region, year in VERIFIED_COORDINATES[:2]:
        for months in (1, 2, 11, 13):
            case_id = "boundary-{}-{}-dw{:02d}".format(region, year, months)
            out.append(_build_case(
                case_id, region, year, "mutual_agreement",
                months, 0, "below", "5", "standard", 28, False, rng,
            ))

    # 6) 三种工时制度（加班引擎口径）
    for region, year in VERIFIED_COORDINATES[:2]:
        for system in WORK_SYSTEMS:
            case_id = "boundary-{}-{}-ws-{}".format(region, year, system)
            out.append(_build_case(
                case_id, region, year, "mutual_agreement",
                24, 0, "below", "5", system, 15, True, rng,
            ))

    for item in out:
        item["profile"] = "boundary"
    return out


PROFILES = {
    "pilot": _pilot_cases,
    "boundary": _boundary_cases,
}


def _payload(profile, items):
    # type: (str, list) -> dict
    return {
        "schema_version": 1,
        "profile": profile,
        "seed": SEEDS[profile],
        "generator": "tools/gen_cases.py",
        "truth_source": "lcc/benchmark/cases.py",
        "note": ("合成雇佣档案 + 真值库（完全虚构）。input_facts 可直接喂 "
                 "`lcc calc`（CLI 自动取 input_facts）。真值由 lcc/benchmark/cases.py "
                 "单一实现源产出；禁手改，改动走生成器重生成。"),
        "count": len(items),
        "cases": items,
    }


def serialize(payload):
    # type: (dict) -> bytes
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    return (text + "\n").encode("utf-8")


def generate():
    # type: () -> list
    if not os.path.isdir(TRUTH_DIR):
        os.makedirs(TRUTH_DIR)
    written = []
    for profile, builder in PROFILES.items():
        items = builder()
        seen = set()
        for item in items:
            if item["case_id"] in seen:
                raise SystemExit("case_id 重复（会静默覆盖）: {}".format(item["case_id"]))
            seen.add(item["case_id"])
        path = os.path.join(TRUTH_DIR, "cases-{}.json".format(profile))
        with open(path, "wb") as handle:
            handle.write(serialize(_payload(profile, items)))
        written.append(path)
    return written


def check():
    # type: () -> int
    problems = []
    for profile, builder in PROFILES.items():
        path = os.path.join(TRUTH_DIR, "cases-{}.json".format(profile))
        if not os.path.isfile(path):
            problems.append("缺失: cases-{}.json".format(profile))
            continue
        with open(path, "rb") as handle:
            actual = handle.read()
        if actual != serialize(_payload(profile, builder())):
            problems.append("位级不一致: cases-{}.json".format(profile))
    if problems:
        for item in problems:
            sys.stderr.write("{}\n".format(item))
        return 1
    sys.stdout.write("FROZEN_TRUTH_OK\n")
    return 0


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="合成雇佣档案 + 真值库生成器")
    parser.add_argument("--check", action="store_true", help="校验再生成位级一致")
    args = parser.parse_args(argv)

    if args.check:
        return check()

    written = generate()
    for path in written:
        with open(path, "r", encoding="utf-8") as handle:
            count = json.load(handle).get("count")
        sys.stdout.write("写入 {}（{} 条）\n".format(
            os.path.relpath(path, ROOT).replace("\\", "/"), count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
