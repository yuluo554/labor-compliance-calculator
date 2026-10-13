"""命令行入口（plan/03 §六；退出码锁进 tests/test_cli_exit_codes.py）。

子命令：
  ``lcc params``  参数库概览（坐标清单 + 核对状态）
  ``lcc doctor``  环境与数据自检（数据目录定位 / 条款库 / 参数包 / 门控）
  ``lcc calc``    按输入 JSON 计算（四模块引擎）
  ``lcc report``  按输入 JSON 计算并导出测算说明（Markdown / XLSX）
  ``lcc gui``     启动桌面界面（惰性导入 PySide6，缺依赖给安装提示）

退出码：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from ._stdio import _ensure_utf8_stdio
from .errors import EXIT_DEGRADED, EXIT_INPUT_ERROR, EXIT_OK, InputError, LccError

PROG = "lcc"

_STATUS_MARK = {"verified": "[已核对]", "pending": "[待核对]"}


def _print(message=""):
    # type: (str) -> None
    sys.stdout.write("{}\n".format(message))


def _mark(status):
    # type: (str) -> str
    return _STATUS_MARK.get(status, "[未知:{}]".format(status))


# --------------------------------------------------------------------------
# 子命令实现
# --------------------------------------------------------------------------

def cmd_params(args):
    # type: (argparse.Namespace) -> int
    from .pipeline import parameter_overview

    summary = parameter_overview(args.data_dir)
    _print("数据目录: {}".format(summary["data_dir"]))
    _print()

    constants_status = summary["constants_status"]
    _print("法定常数包: {}".format(
        _mark(constants_status) if constants_status else "[缺失]"))
    _print()

    regions = summary["regions"]
    _print("地区主数据（{} 个）:".format(len(regions)))
    if not regions:
        _print("  （空）")
    for item in regions:
        _print("  {code}  {name}  口径={caliber}  {status}".format(
            code=item["code"], name=item["name"], caliber=item["caliber"],
            status=_mark(item["status"])))
    _print()

    rulesets = summary["rulesets"]
    _print("规则包（{} 份）:".format(len(rulesets)))
    if not rulesets:
        _print("  （空）")
    for item in rulesets:
        _print("  {region}/{year}  {name}  {status}".format(
            region=item["region_code"], year=item["year"],
            name=item["region_name"] or item["file"], status=_mark(item["status"])))
    _print()
    _print("提示：status=待核对的参数包不得进入计算路径（门控拒绝）。")
    return EXIT_OK


def cmd_doctor(args):
    # type: (argparse.Namespace) -> int
    from .pipeline import diagnostics

    _print("劳动用工合规计算引擎 v{} 环境自检".format(__version__))
    _print("-" * 56)
    _print("Python: {} ({})".format(sys.version.split()[0], sys.executable))

    report = diagnostics(args.data_dir)
    ok = True

    if report["data_dir_error"]:
        _print("[FAIL] 数据目录未找到")
        _print("       {}".format(report["data_dir_error"]))
        return EXIT_INPUT_ERROR
    _print("[OK]   数据目录: {}".format(report["data_dir"]))

    if report["library_error"]:
        ok = False
        _print("[FAIL] 条款库: {}".format(report["library_error"]))
    else:
        _print("[OK]   条款库: {} 条（待核对 {} 条）".format(
            report["library_count"], report["library_pending"]))

    if report["constants_error"]:
        ok = False
        _print("[FAIL] 法定常数包: {}".format(report["constants_error"]))
    else:
        _print("[{}] 法定常数包: {}（{} 条）".format(
            "OK" if report["constants_status"] == "verified" else "WARN",
            report["constants_status"], report["constants_count"]))

    _print("[OK]   规则包文件: {} 份".format(report["ruleset_files"]))
    for name, message in report["ruleset_errors"]:
        ok = False
        _print("[FAIL] {}: {}".format(name, message))
    _print("[OK]   规则包坐标/文件名一致性校验通过（已核对 {} / {} 份）".format(
        report["verified_rulesets"], report["ruleset_files"]))

    _print("-" * 56)
    if ok:
        _print("自检结论：骨架通路正常。")
        if report["verified_rulesets"] == 0:
            _print("注意：暂无已核对参数包 → 计算路径会被门控拒绝（这是预期的纪律行为，见 M1）。")
        return EXIT_OK
    _print("自检结论：存在失败项，见上方 [FAIL]。")
    return EXIT_DEGRADED


def _load_case(args):
    # type: (argparse.Namespace) -> tuple
    """读输入 JSON → 校验为 :class:`lcc.model.CaseInput`。

    支持直接喂真值库记录文件（参数卡在其 ``input_facts`` 字段下）。校验经
    :func:`lcc.pipeline.build_case`（编排层统一入口）；错误一律
    :class:`~lcc.errors.InputError`（exit 2）。
    """
    from .pipeline import build_case

    if not os.path.isfile(args.input):
        raise InputError("输入文件不存在: {}".format(args.input))

    with open(args.input, "r", encoding="utf-8") as handle:
        try:
            raw = json.load(handle)
        except ValueError as exc:
            raise InputError("输入 JSON 解析失败: {}".format(exc))

    # 支持直接喂真值库记录文件（参数卡在其 input_facts 字段下）
    if isinstance(raw, dict) and "input_facts" in raw and "employment" not in raw:
        raw = raw["input_facts"]

    return build_case(raw), args.input


def _run_calc(args):
    # type: (argparse.Namespace) -> object
    """CLI 与 ``report`` 共用的计算通路（编排一律经 :mod:`lcc.pipeline`）。"""
    from .pipeline import build_request, compute_full_calc

    case, _path = _load_case(args)
    modules = tuple(args.modules) if getattr(args, "modules", None) else None
    request = build_request(
        case, modules=modules, data_dir=args.data_dir, preview=bool(args.preview)
    )
    return compute_full_calc(request)


def cmd_calc(args):
    # type: (argparse.Namespace) -> int
    from .pipeline import module_label

    result = _run_calc(args)

    _print("计算坐标: {} / {} 年（{}）".format(
        result.coordinate[0], result.coordinate[1], result.region_name or "未登记名称"))
    _print("规则包状态: {}".format(_mark(result.ruleset_status)))
    _print()

    if result.preview:
        _print("参数来源:")
        for name, source in result.param_sources.items():
            _print("  {name}: {publisher} {year} {url}".format(
                name=name, publisher=source.get("publisher") or "（未登记）",
                year=source.get("published_year") or "", url=source.get("url") or ""))
        _print()
    else:
        for name in result.modules:
            payload = result.modules.get(name)
            if payload is None:
                continue
            amount = payload.get("amount")
            _print("{}: {}".format(
                module_label(name),
                "{} 元".format(amount) if amount is not None else "（无金额结论）"))

    if result.basis:
        _print()
        _print("适用依据:")
        for clause in result.basis:
            _print("  - {} {}".format(clause["citation"], clause["title"]))

    for notice in result.notices:
        _print()
        _print("说明: {}".format(notice))

    _print()
    _print(result.disclaimer)
    # 降级语义（plan/03 §六、plan/04 §八）：预览模式不输出金额结论 → exit 1
    return EXIT_DEGRADED if result.preview else EXIT_OK


def cmd_report(args):
    # type: (argparse.Namespace) -> int
    """计算并导出测算说明（Markdown / XLSX）；内容与 GUI 导出同源（FR-6）。"""
    from .report import write_report

    result = _run_calc(args)
    try:
        written = write_report(result, args.output)
    except LccError as exc:
        sys.stderr.write("{}\n".format(exc.render()))
        return int(exc.exit_code)

    _print("已导出测算说明: {}".format(written))
    _print("格式: {}".format(os.path.splitext(written)[1].lstrip(".")))
    _print()
    _print(result.disclaimer)
    return EXIT_DEGRADED if result.preview else EXIT_OK


def cmd_gui(args):
    # type: (argparse.Namespace) -> int
    """启动桌面界面。

    PySide6 缺失时由 :func:`lcc.gui.app.run` 给出安装提示并 exit 2（不崩溃）；
    依赖就绪则进入事件循环，窗口关闭后 exit 0。惰性导入纪律见
    ``tests/test_repo_gates.py::test_cli_optional_deps_are_lazy_and_guarded``。
    """
    from .gui.app import run

    return int(run(args.data_dir))


# --------------------------------------------------------------------------
# 参数解析
# --------------------------------------------------------------------------

def build_parser():
    # type: () -> argparse.ArgumentParser
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="劳动用工合规计算引擎（全本地、零上传）：经济补偿/赔偿金、加班费、"
                    "未休年休假折算、未签劳动合同二倍工资 + 地区×年度参数库",
    )
    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))
    parser.add_argument("--data-dir", default=None, help="数据目录（默认自动定位）")
    subparsers = parser.add_subparsers(dest="command")

    sub = subparsers.add_parser("params", help="参数库概览（坐标清单 + 核对状态）")
    sub.set_defaults(func=cmd_params)

    sub = subparsers.add_parser("doctor", help="环境与数据自检")
    sub.set_defaults(func=cmd_doctor)

    sub = subparsers.add_parser("calc", help="按输入 JSON 计算")
    sub.add_argument("input", help="输入 JSON 路径（支持真值库记录文件，自动取 input_facts）")
    sub.add_argument("--modules", nargs="+", default=None,
                     choices=["severance", "overtime", "annual_leave", "double_wage"],
                     help="只跑指定模块（默认全跑）")
    sub.add_argument("--preview", action="store_true",
                     help="预览模式：门控命中时仅展示参数元信息，不输出金额")
    sub.set_defaults(func=cmd_calc)

    sub = subparsers.add_parser("report", help="计算并导出测算说明（Markdown / XLSX）")
    sub.add_argument("input", help="输入 JSON 路径（支持真值库记录文件，自动取 input_facts）")
    sub.add_argument("--output", required=True,
                     help="输出文件路径（.md → Markdown；.xlsx → 需 openpyxl）")
    sub.add_argument("--modules", nargs="+", default=None,
                     choices=["severance", "overtime", "annual_leave", "double_wage"],
                     help="只算指定模块（默认全跑）")
    sub.add_argument("--preview", action="store_true",
                     help="预览模式：门控命中时仅展示参数元信息，不输出金额")
    sub.set_defaults(func=cmd_report)

    sub = subparsers.add_parser("gui", help="启动桌面界面（需 PySide6）")
    sub.set_defaults(func=cmd_gui)

    return parser


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_INPUT_ERROR

    try:
        return int(args.func(args))
    except LccError as exc:
        sys.stderr.write("{}\n".format(exc.render()))
        return int(exc.exit_code)
    except KeyboardInterrupt:
        sys.stderr.write("已中断\n")
        return EXIT_DEGRADED


if __name__ == "__main__":
    sys.exit(main())