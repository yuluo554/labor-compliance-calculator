"""命令行入口（plan/03 §六；退出码锁进 tests/test_cli_exit_codes.py）。

子命令：
  ``lcc params``  参数库概览（坐标清单 + 核对状态）
  ``lcc doctor``  环境与数据自检（数据目录定位 / 条款库 / 参数包 / 门控）
  ``lcc calc``    按输入 JSON 计算（M0 骨架：门控与坐标已可跑，引擎未实现时明确提示）
  ``lcc gui``     启动桌面界面（惰性导入 PySide6，缺依赖给安装提示）

退出码：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误。
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from ._stdio import _ensure_utf8_stdio
from . import data_paths, params
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
    summary = params.summarize(args.data_dir)
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
    ok = True
    _print("劳动用工合规计算引擎 v{} 环境自检".format(__version__))
    _print("-" * 56)

    _print("Python: {} ({})".format(sys.version.split()[0], sys.executable))

    try:
        data_dir = data_paths.find_data_dir(args.data_dir)
        _print("[OK]   数据目录: {}".format(data_dir))
    except FileNotFoundError as exc:
        _print("[FAIL] 数据目录未找到")
        _print("       {}".format(exc))
        return EXIT_INPUT_ERROR

    try:
        from .law import load_library

        law_library = load_library(data_dir)
        pending = law_library.pending_ids()
        _print("[OK]   条款库: {} 条（待核对 {} 条）".format(
            len(law_library.ids()), len(pending)))
    except LccError as exc:
        ok = False
        _print("[FAIL] 条款库: {}".format(exc.message))

    try:
        constants = params.load_constants(data_dir)
        _print("[{}] 法定常数包: {}（{} 条）".format(
            "OK" if constants.status == "verified" else "WARN",
            constants.status, len(constants.entries())))
    except LccError as exc:
        ok = False
        _print("[FAIL] 法定常数包: {}".format(exc.message))

    files = params.list_ruleset_files(data_dir)
    _print("[OK]   规则包文件: {} 份".format(len(files)))

    verified = 0
    for path in files:
        import os

        try:
            ruleset = params.load_ruleset(
                *params.RULES_FILENAME_RE.match(os.path.basename(path)).group("region", "year"),
                data_dir=data_dir,
            )
        except LccError as exc:
            ok = False
            _print("[FAIL] {}: {}".format(os.path.basename(path), exc.message))
            continue
        if ruleset.status == "verified":
            verified += 1
    _print("[OK]   规则包坐标/文件名一致性校验通过（已核对 {} / {} 份）".format(
        verified, len(files)))

    _print("-" * 56)
    if ok:
        _print("自检结论：骨架通路正常。")
        if verified == 0:
            _print("注意：暂无已核对参数包 → 计算路径会被门控拒绝（这是预期的纪律行为，见 M1）。")
        return EXIT_OK
    _print("自检结论：存在失败项，见上方 [FAIL]。")
    return EXIT_DEGRADED


def cmd_calc(args):
    # type: (argparse.Namespace) -> int
    import os

    from .model import CaseInput
    from .pipeline import CalcRequest, compute_full_calc, module_label

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

    case = CaseInput.from_dict(raw)
    modules = tuple(args.modules) if args.modules else None
    request = CalcRequest(
        case=case,
        modules=modules or CalcRequest.__dataclass_fields__["modules"].default,
        data_dir=args.data_dir,
        preview=bool(args.preview),
    )

    result = compute_full_calc(request)

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
        for name in request.modules:
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
    return EXIT_OK


def cmd_gui(args):
    # type: (argparse.Namespace) -> int
    """启动桌面界面。

    惰性导入：PySide6 缺失时打印安装提示并 exit 2（不崩溃）；
    依赖就绪后交给 :func:`lcc.gui.app.run`（M0 阶段明确报里程碑）。
    """
    try:
        import PySide6  # noqa: F401
    except ImportError as exc:
        _print("桌面界面需要 PySide6，请先安装：")
        _print("    python -m pip install -e \".[gui]\"")
        _print("（原因：{}）".format(exc))
        return EXIT_INPUT_ERROR

    from .gui.app import run

    return run(args.data_dir)


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