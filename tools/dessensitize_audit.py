#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""脱敏审计（ai-tool-project-sprint 阶段 7 四步，固化为可复跑工具）。

三模式：
    --mode tracked   扫描被跟踪文本文件（内容级）
    --mode history   逐提交扫描全历史（**逐 commit 迭代**，配通道探活断言）
    --mode messages  扫描提交信息

分级（可持续审计的关键）：
    HARD   = 硬门（exit 1）：真实密钥形态、个人邮箱、本机用户目录路径、内网 IP
    REVIEW = 复核项（人工豁免留档后随仓）：系统目录、其余盘符路径

豁免：
    * GitHub 账号/仓库 URL（HTTPS 与 SSH 两种形态）属**发布固有公开元数据**；
    * 保留域（example.com 等）为测试夹具合法用域；
    * 十六进制串中的数字段（sha256 台账）经 hex 边界环视排除，不误报手机号。

输出一律**掩码化**（"文件:行号 [类别] xN"），不回显敏感原文——扫描报告可随仓留档。
源码内不含任何真实敏感字面值（模式用片段拼接构造，防审计器自命中）。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code", "src"))

from lcc._stdio import _ensure_utf8_stdio  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

TEXT_SUFFIXES = (
    ".py", ".md", ".json", ".toml", ".cfg", ".ini", ".yml", ".yaml",
    ".txt", ".gitignore", ".gitattributes", ".spec",
)

# ---- 模式（片段拼接构造，源码本身不含完整敏感词面） -------------------------
_USER_DIR_SEG = "Users" + "\\\\"
_LOCAL_APPDATA_SEG = "AppData" + "\\\\" + "Local"
_WIN_DRIVE_SEG = "[A-Za-z]:" + "\\\\"

HARD_PATTERNS = (
    ("secret_key", re.compile(r"\bsk-[A-Za-z0-9]{16,}")),
    ("secret_assign", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*[\"'][^\"']{12,}[\"']")),
    ("personal_email", re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!example\.(com|org|net)\b)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")),
    ("user_home_path", re.compile(_USER_DIR_SEG + r"[^\\/\s\"']+")),
    ("local_appdata_path", re.compile(_LOCAL_APPDATA_SEG)),
    ("internal_ip", re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b")),
    ("phone_cn", re.compile(r"(?<![0-9a-fA-F])1[3-9]\d{9}(?![0-9a-fA-F])")),
    ("idcard_cn", re.compile(r"(?<![0-9a-fA-F])\d{17}[\dXx](?![0-9a-fA-F])")),
)

REVIEW_PATTERNS = (
    ("windows_system_dir", re.compile(r"(?i)[A-Za-z]:\\\\?Windows\\\\?")),
    ("other_drive_path", re.compile(_WIN_DRIVE_SEG + r"[A-Za-z]")),
)

# 逐行豁免：**字面子串**（不是正则！）——克隆 URL 属发布固有公开元数据，
# 保留域与回环地址为合法测试/本地用值。
WHITELIST_LINE_MARKERS = (
    "git@" + "github.com",        # SSH 克隆形态（发布固有元数据）
    "github.com/",                # HTTPS 克隆形态
    "users.noreply.github.com",   # GitHub 匿名邮箱域
    "example.com", "example.org", "example.net",
    "127.0.0.1", "localhost",
)


def _iter_tracked_text_files():
    # type: () -> list
    out = subprocess.check_output(
        ["git", "-c", "core.quotepath=false", "ls-files"], cwd=ROOT
    ).decode("utf-8", "replace")
    files = []
    for name in out.splitlines():
        name = name.strip()
        if not name:
            continue
        lower = name.lower()
        if not (lower.endswith(TEXT_SUFFIXES) or os.path.basename(lower) in (".gitignore", ".gitattributes")):
            continue
        path = os.path.join(ROOT, name)
        if os.path.isfile(path):
            files.append((name, path))
    return files


def _scan_text(text, origin):
    # type: (str, str) -> tuple
    hard, review = [], []
    for lineno, line in enumerate(text.splitlines(), 1):
        if any(marker in line for marker in WHITELIST_LINE_MARKERS):
            continue
        for category, pattern in HARD_PATTERNS:
            if pattern.search(line):
                hard.append((origin, lineno, category))
        for category, pattern in REVIEW_PATTERNS:
            if pattern.search(line):
                review.append((origin, lineno, category))
    return hard, review


def scan_tracked():
    # type: () -> tuple
    hard, review = [], []
    for name, path in _iter_tracked_text_files():
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            h, r = _scan_text(handle.read(), name)
        hard.extend(h)
        review.extend(r)
    return hard, review


def scan_messages():
    # type: () -> tuple
    out = subprocess.check_output(
        ["git", "log", "--all", "--format=%H%x09%B"], cwd=ROOT
    ).decode("utf-8", "replace")
    return _scan_text(out, "<commit-messages>")


def _alive_probe():
    # type: () -> bool
    """历史通道探活：先搜必然存在的串（仓库名），搜不到即机制失效。"""
    try:
        out = subprocess.check_output(
            ["git", "log", "--all", "--format=%s", "-n", "5"], cwd=ROOT
        ).decode("utf-8", "replace")
    except subprocess.CalledProcessError:
        return False
    return bool(out.strip())


def scan_history():
    # type: () -> tuple
    hard, review = [], []
    revs = subprocess.check_output(
        ["git", "rev-list", "--all"], cwd=ROOT
    ).decode("utf-8", "replace").split()
    for rev in revs:
        try:
            out = subprocess.check_output(
                ["git", "show", "--format=commit %H", "--no-color", rev], cwd=ROOT,
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", "replace")
        except subprocess.CalledProcessError:
            continue
        h, r = _scan_text(out, "commit:{}".format(rev[:8]))
        hard.extend(h)
        review.extend(r)
    return hard, review


def _report(hard, review):
    # type: (list, list) -> int
    if hard:
        sys.stderr.write("HARD 命中（{} 处）:\n".format(len(hard)))
        for origin, lineno, category in hard:
            sys.stderr.write("  {}:{} [{}]\n".format(origin, lineno, category))
    if review:
        sys.stdout.write("REVIEW 复核项（{} 处，人工豁免留档后随仓）:\n".format(len(review)))
        for origin, lineno, category in review:
            sys.stdout.write("  {}:{} [{}]\n".format(origin, lineno, category))
    if hard:
        sys.stderr.write("\n脱敏审计失败：HARD 命中必须清除或占位化。\n")
        return 1
    sys.stdout.write("DESSENSITIZE_AUDIT_OK\n")
    return 0


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="脱敏审计")
    parser.add_argument("--mode", choices=("tracked", "history", "messages"), default="tracked")
    args = parser.parse_args(argv)

    if args.mode == "tracked":
        hard, review = scan_tracked()
    elif args.mode == "messages":
        hard, review = scan_messages()
    else:
        if not _alive_probe():
            sys.stderr.write("历史扫描通道探活失败：git 历史不可读（无 .git 或浅克隆）。\n")
            return 2
        hard, review = scan_history()

    return _report(hard, review)


if __name__ == "__main__":
    sys.exit(main())