#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键构建发布产物（M5-5）：双 exe（onedir）+ 自动验证。

步骤：
  1. 校验 ``lcc.packaging.build_datas()`` 白名单（数据齐全）；
  2. 依次构建 ``tools/lcc-cli.spec`` 与 ``tools/lcc-gui.spec``；
  3. 调 ``tools/verify_package.py`` 做中立目录 + 最小环境验证。

用法：
    py -3.12 -X utf8 tools/build_release.py            # 构建 + 验证
    py -3.12 -X utf8 tools/build_release.py --no-verify
    py -3.12 -X utf8 tools/build_release.py --only cli

**解释器选择**：PyInstaller 5.13（本机 3.8 自带）无法解析 PySide6 6.6 的字节码
（``Instruction object is not iterable``）→ GUI 打包必须用 PyInstaller ≥6；
本机 3.12 装的是 6.22.3，故发布构建用 ``py -3.12``。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "code", "src"))

try:
    from lcc._stdio import _ensure_utf8_stdio
except ImportError:  # 兜底
    def _ensure_utf8_stdio(stream_names=("stdout", "stderr")):
        # type: (object) -> None
        for name in stream_names:
            stream = getattr(sys, name, None)
            if stream is None:
                continue
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8")
                except (ValueError, OSError):
                    pass

SPECS = {
    "cli": "tools/lcc-cli.spec",
    "gui": "tools/lcc-gui.spec",
}

# openpyxl 的可选图像/XML 依赖（约 17 MB）；XLSX 写出路径只用 stdlib，spec 已排除。
FORBIDDEN_BUNDLE_DIRS = ("PIL", "lxml")


def _log(message):
    # type: (str) -> None
    sys.stdout.write(message + "\n")


def check_datas():
    # type: () -> bool
    from lcc.packaging import build_datas, build_datas_manifest

    try:
        build_datas(ROOT)
    except FileNotFoundError as exc:
        sys.stderr.write("数据白名单校验失败: {}\n".format(exc))
        return False
    manifest = build_datas_manifest(ROOT)
    _log("数据白名单（{} 项）:".format(len(manifest)))
    for item in manifest:
        _log("  {} -> {}".format(item["source"], item["dest"]))
    return True


def build(spec_key):
    # type: (str) -> int
    spec = os.path.join(ROOT, SPECS[spec_key])
    _log("\n== 构建 {} ==".format(spec_key))
    argv = [
        sys.executable, "-X", "utf8", "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build"),
        spec,
    ]
    result = subprocess.run(argv, cwd=ROOT)
    return result.returncode


def verify():
    # type: () -> int
    _log("\n== 验证打包物（中立目录 + 最小环境）==")
    argv = [sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "verify_package.py")]
    return subprocess.run(argv, cwd=ROOT).returncode


def check_bundle_layout():
    # type: () -> bool
    """构建后断言：dist 内不得出现 PIL/ 或 lxml/ 目录（spec excludes 的兜底守门）。"""
    hits = []
    for name in ("lcc-cli", "lcc-gui"):
        root = os.path.join(ROOT, "dist", name)
        if not os.path.isdir(root):
            continue
        for current, dirs, _files in os.walk(root):
            for dirname in dirs:
                if dirname in FORBIDDEN_BUNDLE_DIRS:
                    hits.append(os.path.relpath(os.path.join(current, dirname), ROOT))
    if hits:
        sys.stderr.write("\n产物检查失败：不应出现的依赖目录:\n")
        for hit in hits:
            sys.stderr.write("  {}\n".format(hit))
        return False
    _log("\n产物检查：无 PIL/ 或 lxml/ 目录。")
    return True


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="构建并验证发布产物（onedir 双 exe）")
    parser.add_argument("--only", choices=sorted(SPECS), default=None,
                        help="只构建一个产物（默认两个都建）")
    parser.add_argument("--no-verify", action="store_true", help="跳过打包后验证")
    args = parser.parse_args(argv)

    if not check_datas():
        return 2

    targets = [args.only] if args.only else ["cli", "gui"]
    for target in targets:
        code = build(target)
        if code != 0:
            sys.stderr.write("\n构建 {} 失败（exit {}）\n".format(target, code))
            return 1

    if not check_bundle_layout():
        return 1

    if args.no_verify:
        _log("\n构建完成（已跳过验证）。")
        return 0

    code = verify()
    if code != 0:
        sys.stderr.write("\n打包验证未通过（exit {}）\n".format(code))
        return 1
    _log("\nBUILD_RELEASE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
