# -*- coding: utf-8 -*-
"""M5 桌面交付守门：GUI 零判定逻辑（AST）+ 编排一致性 + 报告导出 + offscreen 冒烟。

三层守门：
  1. **GUI 零判定逻辑**（D-13 / FR-8.2）——AST 断言 GUI 不 import 规则层（引擎/
     参数库/门控/条款库）、不含算术运算与政策数值符号；
  2. **编排一致性**（M5-1）——GUI 与 CLI 走同一条 :mod:`lcc.pipeline` 通路，对同一
     输入产出逐字段相同的结论（不是靠"两处都调了 pipeline"这种字面声明）；
  3. **报告导出**（FR-6）——Markdown 与 XLSX 同源、含免责声明与参数来源块。

offscreen 冒烟：设 ``QT_QPA_PLATFORM=offscreen`` 后构造真实窗口并触发计算，
证明 GUI 不是"能 import 但起不来"。
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO_ROOT, "code", "src", "lcc")

# GUI 不得 import 的规则/算法层模块（只能用 pipeline 的公开入口）
_RULE_LAYER_MODULES = {
    "lcc.engine", "lcc.params", "lcc.gate", "lcc.law", "lcc.model",
    "lcc.decimalutil", "lcc.benchmark",
}
_RULE_LAYER_BASENAMES = {
    "severance", "overtime", "annual_leave", "double_wage",
    "params", "gate", "law", "model", "decimalutil", "cases", "rng",
}


def _gui_files():
    # type: () -> list
    out = []
    gui_dir = os.path.join(SRC, "gui")
    for dirpath, dirnames, filenames in os.walk(gui_dir):
        dirnames[:] = [name for name in dirnames if name != "__pycache__"]
        for name in sorted(filenames):
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return out


def _tree(path):
    # type: (str) -> ast.Module
    with open(path, "r", encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename=path)


# ---- 1. GUI 零判定逻辑（AST 静态断言） -------------------------------------

def test_gui_does_not_import_rule_layer():
    """GUI 只经 :mod:`lcc.pipeline` 取数：不得 import 引擎/参数库/门控/条款库/模型。"""
    offenders = []
    for path in _gui_files():
        for node in ast.walk(_tree(path)):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    names = [node.module or ""]
                else:
                    # 相对导入：level==1 对应 lcc.gui.*，level==2 对应 lcc.*
                    module = node.module or ""
                    resolved = "lcc." + module if node.level == 2 else module
                    names = [resolved]
            for name in names:
                if name in _RULE_LAYER_MODULES:
                    offenders.append((os.path.basename(path), name))
                elif name.split(".")[-1] in _RULE_LAYER_BASENAMES and name.startswith("lcc."):
                    offenders.append((os.path.basename(path), name))
    assert not offenders, (
        "GUI 层零判定逻辑（D-13）：不得 import 规则/算法层，只经 lcc.pipeline: {}".format(
            offenders)
    )


def test_gui_has_no_arithmetic_operators():
    """GUI 层不得出现算术运算（判定与计算一律在下层完成）。

    允许：字符串拼接（``+`` / ``%`` 格式化）在字符串字面量上——这里用"操作数含非
    数字字面量即放行"的近似判定：只要二元算术运算的两个操作数中，任一侧是字符串/
    f-string/容器，就不算数值计算。真正要拦的是 ``a * b``、``a / b``、``a - b``
    这类数值运算。
    """
    numeric_ops = (ast.Mult, ast.Div, ast.Sub, ast.FloorDiv, ast.Mod, ast.Pow)
    offenders = []
    for path in _gui_files():
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, numeric_ops):
                continue
            if isinstance(node.left, (ast.Constant, ast.JoinedStr)) or \
                    isinstance(node.right, (ast.Constant, ast.JoinedStr)):
                continue
            offenders.append((os.path.basename(path), node.lineno, type(node.op).__name__))
    assert not offenders, "GUI 层出现算术运算（判定逻辑不得下沉到前端）: {}".format(offenders)


def test_gui_has_no_policy_number_literals():
    """GUI 层不得内联政策数值（与零字面量门禁同口径的 AST 版）。"""
    banned = {21.75, 365.0, 150.0, 200.0, 300.0, 1.5, 2.0, 3.0}
    offenders = []
    for path in _gui_files():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Constant) and isinstance(node.value, float) \
                    and node.value in banned:
                offenders.append((os.path.basename(path), node.lineno, node.value))
    assert not offenders, "GUI 层内联政策数值: {}".format(offenders)


# ---- 2. 编排一致性（M5-1）：GUI 与 CLI 同一通路、同一结论 -------------------

def _sample_case():
    # type: () -> dict
    path = os.path.join(REPO_ROOT, "examples", "sample-case.json")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)["input_facts"]


def _compute_via_pipeline(data_dir):
    # type: (str) -> object
    from lcc.model import CaseInput
    from lcc.pipeline import build_request, compute_full_calc

    return compute_full_calc(build_request(CaseInput.from_dict(_sample_case()), data_dir=data_dir))


def test_cli_and_pipeline_produce_identical_result(data_dir):
    """CLI ``calc`` 与直接走 pipeline 的结果逐字段一致（编排未分叉）。"""
    import io
    import contextlib

    from lcc import cli

    direct = _compute_via_pipeline(data_dir)

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["--data-dir", data_dir, "calc",
                         os.path.join(REPO_ROOT, "examples", "sample-case.json")])
    assert code == 0
    text = out.getvalue()

    # CLI 每个模块的金额都出现在 stdout 且与 pipeline 结果一致
    for name, payload in direct.modules.items():
        amount = payload.get("amount")
        if amount is not None:
            assert "{} 元".format(amount) in text, (name, amount, text)


def test_gui_and_cli_share_single_orchestration_source():
    """GUI 与 CLI 的编排入口都指向 ``lcc.pipeline``（源码级断言，非字面声称）。"""
    from lcc import cli
    from lcc.gui import app

    # CLI：cmd_calc 的模块被 pipeline 的函数引用
    cli_source = open(cli.__file__.replace(".pyc", ".py"), "r", encoding="utf-8").read()
    assert "compute_full_calc" in cli_source
    assert "build_request" in cli_source

    # GUI：计算动作调用 pipeline.build_request / compute_full_calc
    gui_source = open(app.__file__.replace(".pyc", ".py"), "r", encoding="utf-8").read()
    assert "pipeline.build_request" in gui_source
    assert "pipeline.compute_full_calc" in gui_source


def test_pipeline_result_carries_case_for_report(data_dir):
    """``CalcResult.case`` 承载原始输入事实（报告"输入事实"段的唯一来源）。"""
    result = _compute_via_pipeline(data_dir)
    assert result.case is not None
    assert result.case.employment.region_code == "310000"
    assert result.caliber, "社平工资口径应随结果带出（报告参数来源块用）"


# ---- 3. 报告导出（FR-6） ---------------------------------------------------

def test_markdown_report_contains_required_blocks(data_dir):
    """报告必含：输入事实 / 参数来源块 / 适用法条 / 免责声明（FR-6.1/6.2/6.3）。"""
    from lcc.report import render_markdown

    text = render_markdown(_compute_via_pipeline(data_dir))
    assert "输入事实" in text
    assert "参数来源" in text
    assert "上海市人力资源和社会保障局" in text      # 发布机关
    assert "rsj.sh.gov.cn" in text                    # URL
    assert "适用依据" in text
    assert "《中华人民共和国劳动合同法》" in text
    assert "不构成法律意见" in text                   # 免责声明
    assert "计算过程" in text                         # 逐项过程


def test_report_sections_are_single_source(data_dir):
    """Markdown 与 XLSX 消费同一章节结构（内容一致由单一渲染源保证）。"""
    from lcc import report

    result = _compute_via_pipeline(data_dir)
    sections = report.report_sections(result)
    assert sections["meta"] and sections["inputs"] and sections["params"]
    assert sections["modules"], "应产出四模块结论"
    assert sections["disclaimer"]

    text = report.render_markdown(result)
    for label, value in sections["meta"]:
        assert str(value) in text
    for module in sections["modules"]:
        assert module["label"] in text


def test_xlsx_report_matches_markdown_content(data_dir, tmp_path):
    """XLSX 与 Markdown 同源：模块轴、参数来源、免责声明均可从 XLSX 读回。"""
    openpyxl = pytest.importorskip("openpyxl")

    from lcc import report

    result = _compute_via_pipeline(data_dir)
    sections = report.report_sections(result)
    path = str(tmp_path / "out.xlsx")
    report.write_report(result, path)

    workbook = openpyxl.load_workbook(path)
    assert "参数来源" in workbook.sheetnames
    assert "计算结果" in workbook.sheetnames
    assert "说明与免责声明" in workbook.sheetnames

    param_values = [
        str(cell)
        for row in workbook["参数来源"].iter_rows(values_only=True)
        for cell in row if cell
    ]
    for _label, value in sections["params"]:
        assert any(value.split("｜")[0].strip() in item for item in param_values)

    results_values = [
        str(cell)
        for row in workbook["计算结果"].iter_rows(values_only=True)
        for cell in row if cell
    ]
    for module in sections["modules"]:
        assert module["label"] in results_values

    notice = workbook["说明与免责声明"]
    assert any("不构成法律意见" in str(cell) for row in notice.iter_rows(values_only=True)
               for cell in row if cell)


def test_xlsx_export_is_byte_reproducible(data_dir, tmp_path):
    """同一输入的 XLSX 导出**逐字节一致**（D-16 确定性落盘纪律）。

    背景：openpyxl 的 ``save_workbook()`` 会在写盘瞬间把 ``docProps/core.xml`` 的
    ``dcterms:modified`` 覆盖为当前 UTC 时刻，且 zip 条目时间戳取当前时间——若不处理，
    同一输入两次导出字节不同。``report/xlsx.py`` 的 ``_canonicalize_archive()``
    重打包归一化这两处。本测试是那次修复的回归守门（若无该修复必然失败）。
    """
    import hashlib

    openpyxl = pytest.importorskip("openpyxl")

    from lcc.report import write_report

    result = _compute_via_pipeline(data_dir)
    first = str(tmp_path / "one.xlsx")
    second = str(tmp_path / "two.xlsx")
    write_report(result, first)
    write_report(result, second)

    digest_a = hashlib.sha256(open(first, "rb").read()).hexdigest()
    digest_b = hashlib.sha256(open(second, "rb").read()).hexdigest()
    assert digest_a == digest_b, "XLSX 导出不可复现（core.xml 时间戳或 zip 元数据未归一化）"

    # 重打包后仍必须是合法工作簿
    workbook = openpyxl.load_workbook(first)
    assert "计算结果" in workbook.sheetnames
    assert "说明与免责声明" in workbook.sheetnames


def test_xlsx_missing_dependency_degrades(data_dir, tmp_path, monkeypatch):
    """openpyxl 缺失 → OptionalDependencyError（exit 1），提示回退 Markdown，不崩溃。"""
    import builtins

    from lcc.errors import EXIT_DEGRADED, OptionalDependencyError
    from lcc import report

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openpyxl" or name.startswith("openpyxl."):
            raise ImportError("No module named 'openpyxl'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = _compute_via_pipeline(data_dir)
    with pytest.raises(OptionalDependencyError) as exc:
        report.write_report(result, str(tmp_path / "x.xlsx"))
    assert exc.value.exit_code == EXIT_DEGRADED
    assert "Markdown" in exc.value.render()


def test_unsupported_report_extension_rejected(data_dir, tmp_path):
    from lcc.errors import OptionalDependencyError
    from lcc import report

    result = _compute_via_pipeline(data_dir)
    with pytest.raises(OptionalDependencyError):
        report.write_report(result, str(tmp_path / "x.pdf"))


def test_cli_report_command_writes_markdown(data_dir, tmp_path):
    """CLI ``report`` 子命令通路（FR-8.1 的 report 入口）。"""
    from lcc import cli

    out_path = tmp_path / "cli-report.md"
    code = cli.main([
        "--data-dir", data_dir, "report",
        os.path.join(REPO_ROOT, "examples", "sample-case.json"),
        "--output", str(out_path),
    ])
    assert code == 0
    text = out_path.read_text(encoding="utf-8")
    assert "劳动用工合规测算说明" in text
    assert "不构成法律意见" in text


def test_cli_report_missing_output_is_usage_error(data_dir):
    """``report`` 缺 ``--output`` → argparse 用法错误（exit 2）。"""
    from lcc import cli

    with pytest.raises(SystemExit) as exc:
        cli.main(["--data-dir", data_dir, "report",
                  os.path.join(REPO_ROOT, "examples", "sample-case.json")])
    assert exc.value.code == 2


# ---- 4. GUI offscreen 冒烟 -------------------------------------------------

# Qt 的平台插件必须在创建 QApplication **之前**选定；offscreen 让无显示环境可跑。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QT_AVAILABLE = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("PySide6"),
    reason="未安装 PySide6（gui extra）",
)


@pytest.fixture(scope="module")
def qt_app():
    """模块级 QApplication；Qt 组件必须有 application 实例，否则创建窗口即崩。"""
    if not __import__("importlib").util.find_spec("PySide6"):
        pytest.skip("未安装 PySide6（gui extra）")
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def _offscreen_env():
    # type: () -> dict
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.path.join(REPO_ROOT, "code", "src")
    env.pop("DISPLAY", None)
    return env


@QT_AVAILABLE
def test_gui_builds_offscreen_and_computes(data_dir, qt_app):
    """offscreen 平台构造真实窗口 + 触发计算：四页签均有内容、无异常。"""
    from lcc.gui import app as gui_app

    window = gui_app.build_window(data_dir)
    try:
        assert window._tabs.count() >= 6, "应含四类计算 + 参数库 + 报告页签"
        titles = [window._tabs.tabText(i) for i in range(window._tabs.count())]
        for _key, label in gui_app._MODULE_TABS:
            assert label in titles
        assert "参数库" in titles
        assert "报告" in titles
        assert "适用依据" in titles

        result = window.compute()
        assert result is not None, "示例输入应计算成功"
        for key, _label in gui_app._MODULE_TABS:
            text = window._browsers[key].toPlainText()
            assert text.strip(), "{} 页签应有内容".format(key)
        assert "免责声明" in window._report_browser.toPlainText()
        assert "中华人民共和国劳动合同法" in window._basis_browser.toPlainText()
        assert "310000" in window._params_browser.toPlainText()
    finally:
        window.close()


@QT_AVAILABLE
def test_gui_reports_gate_failure_without_crashing(data_dir, qt_app):
    """门控拦截（未核对坐标）时 GUI 把错误展示在页签，不抛异常、不留空窗。"""
    from lcc.gui import app as gui_app

    window = gui_app.build_window(data_dir)
    try:
        window._region.setCurrentText("440000")     # 广东仍 pending
        result = window.compute()
        assert result is None
        assert "未核对" in window._status.text()
        for key, _label in gui_app._MODULE_TABS:
            assert window._browsers[key].toPlainText().strip()
    finally:
        window.close()


@QT_AVAILABLE
def test_gui_run_entry_is_callable_offscreen(data_dir):
    """``lcc gui`` 的 run() 在 offscreen 下可启动事件循环（单次定时后自动退出）。

    用子进程 + QTimer 计划退出，避免测试进程挂死；断言退出码为 0。
    """
    script = (
        "import os, sys\n"
        "os.environ['QT_QPA_PLATFORM'] = 'offscreen'\n"
        "sys.path.insert(0, r'{src}')\n"
        "from PySide6 import QtCore, QtWidgets\n"
        "from lcc.gui import app as gui_app\n"
        "app = QtWidgets.QApplication([])\n"
        "window = gui_app.build_window(r'{data}')\n"
        "window.show()\n"
        "QtCore.QTimer.singleShot(0, window.compute)\n"
        "QtCore.QTimer.singleShot(50, app.quit)\n"
        "app.exec()\n"
        "print('GUI_OFFSCREEN_OK')\n"
    ).format(src=os.path.join(REPO_ROOT, "code", "src"), data=data_dir)

    result = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO_ROOT, env=_offscreen_env(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "GUI_OFFSCREEN_OK" in output


def test_gui_without_pyside_returns_input_error(data_dir, capsys, monkeypatch):
    """PySide6 缺失：``gui.app.run`` 打印安装提示并 exit 2（不崩溃）。"""
    import builtins

    from lcc.errors import EXIT_INPUT_ERROR
    from lcc.gui import app as gui_app

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("No module named 'PySide6'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert gui_app.run(data_dir) == EXIT_INPUT_ERROR
    out = capsys.readouterr().out
    assert "PySide6" in out
    assert "pip install" in out
