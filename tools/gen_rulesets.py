#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""规则包生成器：从地区主数据 × 年度区间生成 ``data/rules/ruleset-<region>-<year>.json`` 骨架。

纪律（plan/05 §1.3、NFR-2）：
  * 产出为**冻结产物**，禁手改——改需求走本生成器整目录重生成；
  * 生成骨架全部 ``status=pending``、数值占位 ``"0.00"``、来源字段为空
    → **未核对不得进入计算路径**（门控拒绝，这是设计行为不是缺陷）；
  * 确定性落盘：``write_bytes`` + 显式 ``\\n``（不用 ``write_text``，避免 CRLF 漂移）；
    产物**不含时间戳** → 两次运行逐字节一致（配 tests/test_frozen_products.py 守门）。

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

from lcc._stdio import _ensure_utf8_stdio  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA_DIR = os.path.join(ROOT, "data")
REGIONS_FILE = os.path.join(DATA_DIR, "regions", "regions.json")
RULES_DIR = os.path.join(DATA_DIR, "rules")

# 骨架生成的年度区间（M1 逐条核对后置 verified；区间外年度按需追加）
YEARS = (2025, 2026)


def load_regions():
    # type: () -> list
    with open(REGIONS_FILE, "r", encoding="utf-8") as handle:
        return json.load(handle).get("regions") or []


def empty_source(publisher=None):
    # type: (object) -> dict
    return {
        "publisher": publisher,
        "published_year": None,
        "doc_no": None,
        "url": None,
        "retrieved_at": None,
    }


def build_ruleset(region, year):
    # type: (dict, int) -> dict
    """构造一份规则包骨架（全部 pending）。"""
    code = str(region["code"])
    name = str(region["name"])
    return {
        "schema_version": 1,
        "region_code": code,
        "region_name": name,
        "year": int(year),
        "generated_by": "tools/gen_rulesets.py",
        "status": "pending",
        "note": "骨架：数值与来源待 M1 逐条核对官方发布后填入并置 status=verified；禁手改，改动走生成器重生成。",
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
                "adjusted_workdays": [],
                "status": "pending",
                "source": empty_source("国务院办公厅"),
                "note": "法定节假日（days）与调休上班日（adjusted_workdays），格式 YYYY-MM-DD。",
            },
        },
    }


def serialize(payload):
    # type: (dict) -> bytes
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    return (text + "\n").encode("utf-8")


def generate():
    # type: () -> list
    """生成全部规则包骨架；返回写出的文件路径列表。"""
    if not os.path.isdir(RULES_DIR):
        os.makedirs(RULES_DIR)
    written = []
    for region in load_regions():
        for year in YEARS:
            filename = "ruleset-{}-{}.json".format(region["code"], year)
            path = os.path.join(RULES_DIR, filename)
            with open(path, "wb") as handle:
                handle.write(serialize(build_ruleset(region, year)))
            written.append(path)
    return written


def check():
    # type: () -> int
    """校验「再生成位级一致」：现有产物与重新生成的字节完全相同。"""
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
            if actual != serialize(build_ruleset(region, year)):
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
    parser = argparse.ArgumentParser(description="规则包骨架生成器")
    parser.add_argument("--check", action="store_true", help="校验再生成位级一致")
    args = parser.parse_args(argv)

    if args.check:
        return check()

    written = generate()
    for path in written:
        sys.stdout.write("写入 {}\n".format(os.path.relpath(path, ROOT).replace("\\", "/")))
    sys.stdout.write("共 {} 份规则包骨架（全部 status=pending，待 M1 核对）\n".format(len(written)))
    return 0


if __name__ == "__main__":
    sys.exit(main())