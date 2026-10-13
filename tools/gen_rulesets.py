#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""规则包生成器：从地区主数据 × 年度区间生成 ``data/rules/ruleset-<region>-<year>.json``。

纪律（plan/05 §1.3、NFR-2）：
  * 产出为**冻结产物**，禁手改——改需求走本生成器整目录重生成；
  * **未核对坐标**：骨架全部 ``status=pending``、数值占位 ``"0.00"``、来源字段为空
    → **未核对不得进入计算路径**（门控拒绝，这是设计行为不是缺陷）；
  * **已核对坐标**：从 ``data/sources/verified-params.json`` 合并已核对数值与来源，
    整包与子项置 ``status=verified``（人工核对留痕见该文件 + data/README.md 台账）；
  * 确定性落盘：``write_bytes`` + 显式 ``\\n``（不用 ``write_text``，避免 CRLF 漂移）；
    产物**不含时间戳** → 两次运行逐字节一致（配 tests/test_repo_gates.py 守门）。

用法：
    py -X utf8 tools/gen_rulesets.py            # 生成（幂等覆盖）
    py -X utf8 tools/gen_rulesets.py --check    # 只校验再生成位级一致
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

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA_DIR = os.path.join(ROOT, "data")
REGIONS_FILE = os.path.join(DATA_DIR, "regions", "regions.json")
VERIFIED_FILE = os.path.join(DATA_DIR, "sources", "verified-params.json")
RULES_DIR = os.path.join(DATA_DIR, "rules")

# 骨架生成的年度区间（M1 逐条核对后置 verified；区间外年度按需追加）
YEARS = (2025, 2026)

PENDING_NOTE = "骨架：数值与来源待 M1 逐条核对官方发布后填入并置 status=verified；禁手改，改动走生成器重生成。"
VERIFIED_NOTE = "已核对：数值与来源取自 data/sources/verified-params.json（官方原文逐条核对，留痕见 data/README.md 台账）；禁手改，改动走生成器重生成。"


def load_regions():
    # type: () -> list
    with open(REGIONS_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle).get("regions") or []


def load_verified():
    # type: () -> dict
    """已核对参数索引：``{(region_code, year): payload}``。"""
    if not os.path.isfile(VERIFIED_FILE):
        return {}
    with open(VERIFIED_FILE, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    index = {}
    for item in payload.get("params") or []:
        index[(str(item["region_code"]), int(item["year"]))] = item
    return index


def empty_source(publisher=None):
    # type: (object) -> dict
    return {
        "publisher": publisher,
        "published_year": None,
        "doc_no": None,
        "url": None,
        "retrieved_at": None,
    }


def _verified_entry(entry, extra_keys=()):
    # type: (dict, tuple) -> dict
    """构造 verified 条目：值 + 单位 + 状态 + 来源（+ 派生说明）。"""
    result = {
        "value": entry["value"],
        "unit": "CNY/month",
        "status": "verified",
        "source": dict(entry["source"]),
    }
    for key in extra_keys:
        if key in entry:
            result[key] = entry[key]
    if entry.get("derivation_note"):
        result["note"] = entry["derivation_note"]
    return result


def build_ruleset(region, year, verified=None):
    # type: (dict, int, object) -> dict
    """构造一份规则包：命中已核对坐标则 verified，否则 pending 骨架。"""
    code = str(region["code"])
    name = str(region["name"])
    hit = (verified or {}).get((code, int(year)))

    if hit is None:
        return {
            "schema_version": 1,
            "region_code": code,
            "region_name": name,
            "year": int(year),
            "generated_by": "tools/gen_rulesets.py",
            "status": "pending",
            "note": PENDING_NOTE,
            "params": {
                "social_avg_wage_monthly": {
                    "value": "0.00",
                    "unit": "CNY/month",
                    "caliber": region.get("avg_wage_caliber"),
                    "basis_year": int(year) - 1,
                    "status": "pending",
                    "source": empty_source(),
                    "note": "上年度职工月平均工资（三倍封顶基数）；口径须与 regions.json 登记一致。",
                },
                "min_wage_monthly": {
                    "value": "0.00",
                    "unit": "CNY/month",
                    "status": "pending",
                    "source": empty_source(),
                    "note": "当地月最低工资标准（月工资下限用）。",
                },
                "holiday_calendar": {
                    "days": [],
                    "rest_days": [],
                    "adjusted_workdays": [],
                    "status": "pending",
                    "source": empty_source("国务院办公厅"),
                    "note": "法定节假日（days，300%）、调休休息日（rest_days，200%）、调休上班日（adjusted_workdays，150%），格式 YYYY-MM-DD。",
                },
            },
        }

    wage = hit["social_avg_wage_monthly"]
    minw = hit["min_wage_monthly"]
    cal = hit["holiday_calendar"]
    return {
        "schema_version": 1,
        "region_code": code,
        "region_name": name,
        "year": int(year),
        "generated_by": "tools/gen_rulesets.py",
        "status": "verified",
        "note": VERIFIED_NOTE,
        "params": {
            "social_avg_wage_monthly": _verified_entry(
                wage, extra_keys=("caliber", "basis_year")
            ),
            "min_wage_monthly": _verified_entry(minw),
            "holiday_calendar": {
                "days": list(cal["days"]),
                "rest_days": list(cal.get("rest_days") or []),
                "adjusted_workdays": list(cal["adjusted_workdays"]),
                "status": "verified",
                "source": dict(cal["source"]),
                "note": cal.get("derivation_note", ""),
            },
        },
    }


def serialize(payload):
    # type: (dict) -> bytes
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    return (text + "\n").encode("utf-8")


def generate():
    # type: () -> list
    """生成全部规则包；返回写出的文件路径列表。"""
    if not os.path.isdir(RULES_DIR):
        os.makedirs(RULES_DIR)
    verified = load_verified()
    written = []
    for region in load_regions():
        for year in YEARS:
            filename = "ruleset-{}-{}.json".format(region["code"], year)
            path = os.path.join(RULES_DIR, filename)
            with open(path, "wb") as handle:
                handle.write(serialize(build_ruleset(region, year, verified)))
            written.append(path)
    return written


def check():
    # type: () -> int
    """校验「再生成位级一致」：现有产物与重新生成的字节完全相同。"""
    verified = load_verified()
    mismatched = []
    missing = []
    for region in load_regions():
        for year in YEARS:
            filename = "ruleset-{}-{}.json".format(region["code"], year)
            path = os.path.join(RULES_DIR, filename)
            if not os.path.isfile(path):
                missing.append(filename)
                continue
            with open(path, "rb") as handle:
                actual = handle.read()
            if actual != serialize(build_ruleset(region, year, verified)):
                mismatched.append(filename)
    if missing or mismatched:
        for name in missing:
            sys.stderr.write("缺失: {}\n".format(name))
        for name in mismatched:
            sys.stderr.write("位级不一致: {}\n".format(name))
        return 1
    sys.stdout.write("FROZEN_RULESETS_OK\n")
    return 0


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="规则包生成器")
    parser.add_argument("--check", action="store_true", help="校验再生成位级一致")
    args = parser.parse_args(argv)

    if args.check:
        return check()

    verified = load_verified()
    written = generate()
    verified_count = 0
    for path in written:
        name = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as handle:
            if json.load(handle).get("status") == "verified":
                verified_count += 1
        sys.stdout.write("写入 {}\n".format(os.path.relpath(path, ROOT).replace("\\", "/")))
    sys.stdout.write(
        "共 {} 份规则包（已核对 {} 份，其余 status=pending 待 M1 核对）\n".format(
            len(written), verified_count)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())