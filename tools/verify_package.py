#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包产物验证（M5-5）：中立目录 + 剥离环境的 CLI 六连 + GUI offscreen 冒烟。

为什么必须**中立目录 + ``env -i``**：
  * 在仓库根跑 exe 会因 `data/` 回溯命中源码树而"假绿"——真正要验的是**打包物
    自带数据**能否自洽；
  * 继承当前环境会带上 ``PYTHONPATH`` / ``LCC_DATA_DIR`` 等变量，掩盖"冻结态数据
    定位"的缺陷。

本脚本：
  1. 把 ``dist/lcc-cli`` 与 ``dist/lcc-gui`` 复制到临时中立目录（``tempfile``）；
  2. 用**最小环境**（只保留 Windows 必需的 ``SystemRoot`` 等）跑 CLI 六连
     （``params`` / ``doctor`` / ``calc`` 单模块 / ``calc`` 默认四模块 /
     ``calc --preview`` 已核对坐标 / ``calc --preview`` 门控命中）；
  3. 断言退出码语义（0/0/0/0/0/1）与关键输出；
  4. GUI exe 以 offscreen 启动并在短延时后退出（窗口态无 stdout，故只验"能起来"）。

用法：
    py -X utf8 tools/verify_package.py                 # 验证 dist/ 下的两个产物
    py -X utf8 tools/verify_package.py --dist dist     # 指定 dist 目录
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile

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

# Windows 上进程启动必需的最小变量（剥掉 PYTHONPATH/PYTHONHOME 等污染源）
_KEEP_ENV = ("SystemRoot", "SystemDrive", "windir", "TEMP", "TMP",
             "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PATHEXT",
             "COMSPEC", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA",
             "LOCALAPPDATA", "PROGRAMDATA")


def minimal_env(extra=None):
    # type: (object) -> dict
    """只保留系统必需变量的最小环境（显式剔除 PYTHONPATH / LCC_DATA_DIR）。"""
    env = {}
    for name in _KEEP_ENV:
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    env["QT_QPA_PLATFORM"] = "offscreen"
    for name in ("PYTHONPATH", "PYTHONHOME", "LCC_DATA_DIR", "PYTHONSTARTUP"):
        env.pop(name, None)
    if extra:
        env.update(extra)
    return env


def _decode_output(blob):
    # type: (bytes) -> str
    """解码子进程输出：UTF-8 优先，回退到本机首选编码（Windows 中文为 cp936）。

    背景：``_stdio._ensure_utf8_stdio()`` 的纪律是"流自身能编码中文就保持原样"——
    本机中文控制台（cp936）下 exe 会按 GBK 输出，CI（cp1252 管道）下才被 reconfigure
    为 UTF-8。验证脚本两者都要能读，故按 UTF-8 → locale → replace 依次尝试。
    """
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for encoding in ("cp936", "gbk", locale.getpreferredencoding(False), "latin-1"):
        try:
            return blob.decode(encoding)
        except (UnicodeDecodeError, LookupError, TypeError):
            continue
    return blob.decode("utf-8", "replace")


def _run(argv, cwd, timeout=180):
    # type: (list, str, int) -> tuple
    result = subprocess.run(
        argv, cwd=cwd, env=minimal_env(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
    )
    return result.returncode, _decode_output(result.stdout)


def stage(dist_dir, name, target_root):
    # type: (str, str, str) -> str
    """把 onedir 产物复制到中立目录，返回 exe 所在目录。"""
    source = os.path.join(dist_dir, name)
    if not os.path.isdir(source):
        raise FileNotFoundError("未找到打包产物: {}".format(source))
    destination = os.path.join(target_root, name)
    shutil.copytree(source, destination)
    return destination


def _exe(directory, stem):
    # type: (str, str) -> str
    candidate = os.path.join(directory, stem + (".exe" if os.name == "nt" else ""))
    if not os.path.isfile(candidate):
        raise FileNotFoundError("未找到可执行文件: {}".format(candidate))
    return candidate


def verify_cli(work_root):
    # type: (str) -> list
    """CLI 六连（中立目录 + 最小环境）。返回 ``[(命令, 退出码, 是否通过)]``。"""
    cli_dir = _exe(os.path.join(work_root, "lcc-cli"), "lcc")
    sample = os.path.join(ROOT, "examples", "sample-case.json")
    checks = []

    code, out = _run([cli_dir, "params"], work_root)
    checks.append(("params", code, code == 0 and "规则包" in out))

    code, out = _run([cli_dir, "doctor"], work_root)
    checks.append(("doctor", code, code == 0 and "自检结论" in out))

    code, out = _run([cli_dir, "calc", sample, "--modules", "severance"], work_root)
    checks.append(("calc --modules severance", code, code == 0 and "经济补偿" in out))

    code, out = _run([cli_dir, "calc", sample], work_root)
    ok = code == 0 and all(
        label in out for label in ("经济补偿/赔偿金", "加班费", "未休年休假折算", "未签书面劳动合同二倍工资")
    )
    checks.append(("calc（默认四模块）", code, ok))

    # --preview：已核对坐标不降级（exit 0 出金额）；门控命中才降级（exit 1 仅参数）
    code, out = _run([cli_dir, "calc", "--preview", sample], work_root)
    checks.append((
        "calc --preview（已核对坐标）", code,
        code == 0 and "元" in out and "未核对" not in out,
    ))

    with open(sample, "r", encoding="utf-8") as handle:
        pending_payload = json.load(handle)
    pending_payload["input_facts"]["employment"]["region_code"] = "440000"
    pending_sample = os.path.join(work_root, "verify-pending.json")
    with open(pending_sample, "w", encoding="utf-8") as handle:
        json.dump(pending_payload, handle, ensure_ascii=False, indent=2)
    code, out = _run([cli_dir, "calc", "--preview", pending_sample], work_root)
    checks.append((
        "calc --preview（门控命中）", code,
        code == 1 and "预览模式" in out and "未核对" in out,
    ))

    # 报告导出（Markdown 必过；XLSX 视打包时是否含 openpyxl 而定，缺失应优雅降级）
    md_path = os.path.join(work_root, "verify-report.md")
    code, out = _run([cli_dir, "report", sample, "--output", md_path], work_root)
    md_ok = code == 0 and os.path.isfile(md_path)
    if md_ok:
        with open(md_path, "r", encoding="utf-8") as handle:
            md_ok = "不构成法律意见" in handle.read()
    checks.append(("report --output *.md", code, md_ok))

    xlsx_path = os.path.join(work_root, "verify-report.xlsx")
    code, out = _run([cli_dir, "report", sample, "--output", xlsx_path], work_root)
    if code == 0:
        checks.append(("report --output *.xlsx", code, os.path.isfile(xlsx_path)))
    else:
        # openpyxl 未随包 → 必须是**明确提示 + exit 1**（而非崩溃或静默产出）
        degraded = code == 1 and "openpyxl" in out and "Markdown" in out
        checks.append(("report *.xlsx（无 openpyxl 时降级）", code, degraded))

    return checks


def verify_gui(work_root):
    # type: (str) -> tuple
    """GUI exe offscreen 冒烟：能启动即通过（窗口态无 stdout）。

    GUI exe 是 ``console=False``，无法读回输出；改为通过进程退出码判定：以
    ``QT_QPA_PLATFORM=offscreen`` 启动后，用 ``--self-test`` 不可行（GUI 无 CLI），
    故采用「启动 → 短暂等待 → 终止」并断言"进程未立即崩溃"。
    """
    gui_dir = os.path.join(work_root, "lcc-gui")
    gui_exe = _exe(gui_dir, "lcc-gui")
    env = minimal_env({"QTWEBENGINE_DISABLE_SANDBOX": "1"})
    try:
        process = subprocess.Popen(
            [gui_exe], cwd=work_root, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        return (False, "启动失败: {}".format(exc))

    try:
        code = process.wait(timeout=25)
    except subprocess.TimeoutExpired:
        # 仍在运行 = 窗口已起且未崩溃；主动终止并判通过
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
        return (True, "GUI 已启动（offscreen 下运行至主动终止）")

    output = (process.stdout.read() or b"").decode("utf-8", "replace")
    # 窗口态：能立即正常退出（0）或报依赖/数据错误都不算崩溃；
    # 但非零且无任何诊断信息 → 视为启动异常
    if code == 0:
        return (True, "GUI 正常退出（exit 0）")
    return (False, "GUI 异常退出 exit={}: {}".format(code, output.strip()[:400]))


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="打包产物验证（中立目录 + 最小环境）")
    parser.add_argument("--dist", default=os.path.join(ROOT, "dist"), help="dist 目录")
    parser.add_argument("--skip-gui", action="store_true", help="跳过 GUI 冒烟")
    args = parser.parse_args(argv)

    dist_dir = os.path.abspath(args.dist)
    if not os.path.isdir(dist_dir):
        sys.stderr.write("未找到 dist 目录: {}（先跑 tools/build_release.py）\n".format(dist_dir))
        return 2

    failures = []
    with tempfile.TemporaryDirectory(prefix="lcc-verify-") as work_root:
        sys.stdout.write("中立目录: {}\n".format(work_root))
        try:
            stage(dist_dir, "lcc-cli", work_root)
        except FileNotFoundError as exc:
            sys.stderr.write("{}\n".format(exc))
            return 2

        sys.stdout.write("\n== CLI 六连（最小环境）==\n")
        for name, code, ok in verify_cli(work_root):
            sys.stdout.write("[{}] {}（exit {}）\n".format("OK" if ok else "FAIL", name, code))
            if not ok:
                failures.append("cli:{}".format(name))

        if not args.skip_gui:
            sys.stdout.write("\n== GUI 冒烟（offscreen）==\n")
            try:
                stage(dist_dir, "lcc-gui", work_root)
                ok, detail = verify_gui(work_root)
            except FileNotFoundError as exc:
                ok, detail = False, str(exc)
            sys.stdout.write("[{}] lcc-gui: {}\n".format("OK" if ok else "FAIL", detail))
            if not ok:
                failures.append("gui")

    if failures:
        sys.stderr.write("\n打包验证失败：{}\n".format(", ".join(failures)))
        return 1
    sys.stdout.write("\nPACKAGE_VERIFY_OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
