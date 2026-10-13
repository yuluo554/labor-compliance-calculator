#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""零政策字面量门禁（NFR-4 / D-12）。

目的：**杜绝"抄进代码的第二份真相"**。全部法定数值（倍率、天数分档、口径天数、
上限年限/月数、百分比）只能来自 ``data/constants/`` 与 ``data/rules/``；
引擎、基准、前端源码中出现这些数值即为门禁失败——**连 docstring 与注释一起扫**。

扫描面（"计算路径 + 前端"）：
    code/src/lcc/engine/**     四引擎
    code/src/lcc/benchmark/**  基准
    code/src/lcc/gui/**        桌面前端
    code/src/lcc/pipeline.py   编排（不得内联法定数值）

豁免口径（写死，见下 EXEMPT）：
  * **小值**（<100 的整数/小数）属通用编程常量（列表下标、循环、精度位数、
    年月日字段、版本号段），无法与政策数值区分 → 整类豁免，由"数值只能来自
    数据包"的结构性约束（引擎只经 EffectiveRuleset 取数）与代码评审兜底；
  * **精度约定**：金额量化两位小数、``ROUND_HALF_UP`` 属精度约定非政策数值 → 豁免；
  * **日历常数**：年份数字（如 2025/2026）本身不是政策数值 → 豁免；
  * 扫描面**不含** data/（数值的唯一合法住所）、plan/、docs/、tests/（测试需构造
    边界输入，其数值是"输入样本"而非"引擎内联真相"）。

用法：
    py -X utf8 tools/check_no_literals.py           # 扫描，命中即 exit 1
    py -X utf8 tools/check_no_literals.py --list    # 打印禁用 token 与扫描面
"""

from __future__ import annotations

import argparse
import os
import re
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
SRC = os.path.join(ROOT, "code", "src", "lcc")

SCAN_TARGETS = (
    os.path.join(SRC, "engine"),
    os.path.join(SRC, "benchmark"),
    os.path.join(SRC, "gui"),
)
SCAN_FILES = (os.path.join(SRC, "pipeline.py"),)

# 禁用 token：≥100 的政策数值 + 对应百分比串 + 高辨识度小数
# （<100 的小值整类豁免，理由见模块 docstring）
BANNED_TOKENS = (
    "21.75",   # 月计薪天数（年休假/加班日工资口径）
    "365",     # 年休假当年度折算分母
    "150", "200", "300",   # 加班倍率的百分比表述
    "150%", "200%", "300%",
)

# 高辨识度小数（须带小数点，避免撞版本号/下标）
BANNED_DECIMALS = ("1.5", "2.0", "3.0")

# 注释/docstring 里的"引用形态"豁免：形如 §3.1 / 第 47 条 / 条号 / plan 文档编号
_REFERENCE_PATTERNS = (
    re.compile(r"§\s*\d+(?:\.\d+)*"),
    re.compile(r"第\s*[0-9〇一二三四五六七八九十百]+\s*条"),
    re.compile(r"\bplan/\d+"),
    re.compile(r"\bM[0-6]\b"),
    re.compile(r"\bLCL-\d+\b"),
    re.compile(r"\bLL-\d+\b"),
    re.compile(r"\bALR-\d+\b"),
    re.compile(r"\bMOHRSS-ORDER-\d+-ART\d+\b"),
    re.compile(r"v?\d+\.\d+\.\d+"),          # 版本号
    re.compile(r"\b20\d{2}\b"),              # 年份
)

_EXEMPT_LINE_MARKERS = ("noqa", "literal-gate-exempt")


def iter_source_files():
    # type: () -> list
    files = []
    for target in SCAN_TARGETS:
        if not os.path.isdir(target):
            continue
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [name for name in dirnames if name != "__pycache__"]
            for name in sorted(filenames):
                if name.endswith(".py"):
                    files.append(os.path.join(dirpath, name))
    for path in SCAN_FILES:
        if os.path.isfile(path):
            files.append(path)
    return files


def _mask_references(line):
    # type: (str) -> str
    masked = line
    for pattern in _REFERENCE_PATTERNS:
        masked = pattern.sub(" ", masked)
    return masked


def scan_file(path):
    # type: (str) -> list
    """返回命中列表 ``[(行号, token, 行内容)]``。"""
    hits = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for lineno, line in enumerate(handle, 1):
            if any(marker in line for marker in _EXEMPT_LINE_MARKERS):
                continue
            masked = _mask_references(line)
            for token in BANNED_TOKENS:
                if re.search(r"(?<![0-9A-Za-z.])" + re.escape(token) + r"(?![0-9A-Za-z])", masked):
                    hits.append((lineno, token, line.strip()))
            for token in BANNED_DECIMALS:
                if re.search(r"(?<![0-9A-Za-z.])" + re.escape(token) + r"(?![0-9A-Za-z.])", masked):
                    hits.append((lineno, token, line.strip()))
    return hits


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="零政策字面量门禁")
    parser.add_argument("--list", action="store_true", help="列出禁用 token 与扫描面")
    args = parser.parse_args(argv)

    files = iter_source_files()

    if args.list:
        sys.stdout.write("禁用 token（整词匹配）: {}\n".format(", ".join(BANNED_TOKENS)))
        sys.stdout.write("禁用小数: {}\n".format(", ".join(BANNED_DECIMALS)))
        sys.stdout.write("扫描面（{} 个文件）:\n".format(len(files)))
        for path in files:
            sys.stdout.write("  {}\n".format(os.path.relpath(path, ROOT).replace("\\", "/")))
        return 0

    total = 0
    for path in files:
        for lineno, token, content in scan_file(path):
            total += 1
            sys.stdout.write("{}:{} [{}] {}\n".format(
                os.path.relpath(path, ROOT).replace("\\", "/"), lineno, token, content[:100]))

    if total:
        sys.stderr.write(
            "\n零政策字面量门禁失败：{} 处命中。法定数值只能来自 data/constants 与 data/rules，"
            "请改为经 EffectiveRuleset 取数。\n".format(total)
        )
        return 1

    sys.stdout.write("NO_POLICY_LITERALS_OK（扫描 {} 个文件，0 命中）\n".format(len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())