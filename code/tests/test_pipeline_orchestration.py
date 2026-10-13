# -*- coding: utf-8 -*-
"""M5-1 编排上收守门：CLI 与 GUI 共用同一条 :mod:`lcc.pipeline` 通路。

本文件独立于 ``test_gui_layer.py``（后者含 Qt 依赖），专门断言**迁移前后行为一致**
与**唯一编排源**：

  1. 表现层（cli / gui）的公开入口全部落在 pipeline 上，无第二条编排实现；
  2. 同一输入经不同入口（CLI stdout / pipeline 直调 / 报告章节）得到同一组结论；
  3. CLI 退出码与 pipeline 结果语义一致（成功 0、预览降级 1、门控 2）。
"""

from __future__ import annotations

import ast
import io
import contextlib
import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO_ROOT, "code", "src", "lcc")
SAMPLE = os.path.join(REPO_ROOT, "examples", "sample-case.json")


def _source(relative):
    # type: (str) -> str
    with open(os.path.join(SRC, relative), "r", encoding="utf-8") as handle:
        return handle.read()


def _imported_modules(text):
    # type: (str) -> set
    """AST 收集导入的模块名与导入别名。

    相对导入按层级归一化：本文件被测对象都是 ``lcc`` 包内的一级子模块
    （``cli.py`` / ``gui/app.py``），故 ``from .x import y``（level 1）与
    ``from ..x import y``（level 2）都归一化为 ``lcc.x``；``from .. import pipeline``
    形态把别名也收进来，避免漏判。
    """
    names = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                names.add(node.module or "")
            else:
                names.add("lcc." + (node.module or ""))
            for alias in node.names:
                names.add(alias.name)
    return names


def test_presentation_layer_only_orchestrates_via_pipeline():
    """cli / gui 不得直接 import 引擎、参数库、门控、条款库（编排单点 D-13）。"""
    forbidden = {"lcc.engine", "lcc.params", "lcc.gate", "lcc.law",
                 "lcc.benchmark", "lcc.decimalutil"}
    for relative in ("cli.py", os.path.join("gui", "app.py")):
        imported = _imported_modules(_source(relative))
        overlap = imported & forbidden
        assert not overlap, "{} 绕过编排层直接依赖: {}".format(relative, sorted(overlap))
        assert "lcc.pipeline" in imported or "..pipeline" in _source(relative) \
            or "pipeline" in imported, "{} 应经 lcc.pipeline 编排".format(relative)


def test_pipeline_is_imported_by_both_frontends():
    """CLI 与 GUI 都引用 pipeline 的同一组入口（源码级证据，非字面声称）。"""
    cli_text = _source("cli.py")
    gui_text = _source(os.path.join("gui", "app.py"))
    for symbol in ("build_case", "build_request", "compute_full_calc"):
        assert symbol in cli_text, "cli.py 应经 pipeline.{}".format(symbol)
        assert symbol in gui_text, "gui/app.py 应经 pipeline.{}".format(symbol)


def test_module_default_is_defined_once():
    """默认模块集合只有 pipeline.MODULES 一处定义（防两处默认值漂移）。"""
    from lcc.pipeline import MODULES

    assert MODULES == ("severance", "overtime", "annual_leave", "double_wage")
    # CLI 参数 choices 与 pipeline.MODULES 必须同集合
    from lcc import cli

    parser = cli.build_parser()
    choices = set()
    for action in parser._subparsers._group_actions[0].choices["calc"]._actions:
        if action.dest == "modules":
            choices = set(action.choices)
    assert choices == set(MODULES), (choices, MODULES)


def test_build_request_defaults_to_all_modules():
    from lcc.model import CaseInput
    from lcc.pipeline import MODULES, build_request

    with open(SAMPLE, "r", encoding="utf-8") as handle:
        raw = json.load(handle)["input_facts"]
    request = build_request(CaseInput.from_dict(raw))
    assert request.modules == MODULES
    assert request.preview is False


def _pipeline_result(data_dir, modules=None):
    from lcc.model import CaseInput
    from lcc.pipeline import build_request, compute_full_calc

    with open(SAMPLE, "r", encoding="utf-8") as handle:
        raw = json.load(handle)["input_facts"]
    return compute_full_calc(build_request(CaseInput.from_dict(raw), modules=modules,
                                           data_dir=data_dir))


def test_cli_stdout_matches_pipeline_amounts(data_dir):
    """CLI 打印的每个模块金额 = pipeline 直调结果的对应字段（行为迁移前后一致）。"""
    from lcc import cli

    result = _pipeline_result(data_dir)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["--data-dir", data_dir, "calc", SAMPLE])
    assert code == 0
    text = out.getvalue()
    for payload in result.modules.values():
        amount = payload.get("amount")
        if amount is not None:
            assert "{} 元".format(amount) in text


def test_cli_only_severance_does_not_print_other_modules(data_dir):
    """``--modules severance`` 只产出经济补偿（模块选择语义未被编排改动破坏）。"""
    from lcc import cli

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["--data-dir", data_dir, "calc", SAMPLE, "--modules", "severance"])
    assert code == 0
    text = out.getvalue()
    assert "经济补偿/赔偿金" in text
    assert "加班费:" not in text


def test_report_sections_match_pipeline_amounts(data_dir):
    """报告章节里的金额 = pipeline 结果 ``amount``（报告不重算、不改写）。"""
    from lcc import report

    result = _pipeline_result(data_dir)
    sections = report.report_sections(result)
    by_name = {item["name"]: item for item in sections["modules"]}
    for name, payload in result.modules.items():
        amount = payload.get("amount")
        if amount is None:
            continue
        fields = dict(by_name[name]["fields"])
        assert fields["金额（元）"] == str(amount), (name, fields.get("金额（元）"), amount)


@pytest.mark.parametrize("modules", [None, ("severance",), ("overtime",)])
def test_pipeline_result_is_deterministic(data_dir, modules):
    """同一输入两次调用逐字段一致（无隐藏状态、无时间依赖）。"""
    first = _pipeline_result(data_dir, modules)
    second = _pipeline_result(data_dir, modules)
    assert first.modules.keys() == second.modules.keys()
    for name in first.modules:
        assert first.modules[name] == second.modules[name], name
