"""GUI 应用入口——M5 实装（FR-8.2）。

纪律（plan/03 §五.6、D-13）：
  * **GUI 层零判定逻辑**：只经 :mod:`lcc.pipeline` 取数与行事——不 import 引擎/
    参数库/门控/条款库，不做任何数值运算。守门见 ``code/tests/test_gui_layer.py``
    的 AST 断言（无规则层 import、无算术运算符、无政策数值符号）。
  * **PySide6 惰性导入**（缺依赖时给安装提示，不崩溃）：全部 Qt 代码都在
    :func:`build_window` 内部的守卫式导入之后。
  * 页签布局：四类计算 + 参数库 + 报告（FR-8.2）。

``run()`` 返回 CLI 语义的退出码（0 成功 / 2 依赖缺失），供 ``lcc gui`` 复用。
"""

from __future__ import annotations

import html

from .. import __version__
from ..errors import EXIT_OK, EXIT_INPUT_ERROR, LccError, OptionalDependencyError

MILESTONE = "M5"

_INSTALL_HINT = [
    "桌面界面需要 PySide6，请先安装：",
    "    python -m pip install -e \".[gui]\"",
]

# 表单预填值：仅"输入样本"（演示可跑通），不含任何政策数值。
_DEFAULTS = {
    "region_code": "310000",
    "year": "2026",
    "hire_date": "2020-03-01",
    "terminate_date": "2026-06-30",
    "monthly_wages": "12000.00, 12500.00, 12000.00, 11800.00, 13000.00, 12000.00, "
                     "12000.00, 12200.00, 12000.00, 12100.00, 12000.00, 12300.00",
    "work_system": "standard",
    "cumulative_service_years": "6.5",
    "contract_signed_date": "",
    "annual_leave_taken_days": "2",
    "overtime": "2026-05-01, 8\n2026-05-10, 4",
    "ground": "mutual_agreement",
    "notified_30d_in_advance": "（不填）",
}

_MODULE_TABS = (
    ("severance", "经济补偿/赔偿金"),
    ("overtime", "加班费"),
    ("annual_leave", "未休年休假"),
    ("double_wage", "二倍工资"),
)


def _import_qt():
    # type: () -> tuple
    """守卫式惰性导入 PySide6（只在函数内、只在此处）。"""
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError as exc:
        raise OptionalDependencyError(
            _INSTALL_HINT[0], _INSTALL_HINT[1:] + ["（原因：{}）".format(exc)]
        )
    return QtCore, QtGui, QtWidgets


def _escape(value):
    # type: (object) -> str
    return html.escape("" if value is None else str(value))


def _pairs_html(pairs):
    # type: (list) -> str
    rows = []
    for label, value in pairs:
        rows.append(
            "<tr><th align=\"left\">{}</th><td>{}</td></tr>".format(
                _escape(label), _escape(value))
        )
    return "<table border=\"0\" cellspacing=\"0\" cellpadding=\"4\">{}</table>".format(
        "".join(rows))


def _module_html(section):
    # type: (dict) -> str
    """把报告的单个模块章节渲染为 HTML（纯排版，无判定）。"""
    parts = ["<h3>{}</h3>".format(_escape(section["label"]))]
    parts.append(_pairs_html(section["fields"]))
    if section["steps"]:
        items = "".join("<li>{}</li>".format(_escape(step)) for step in section["steps"])
        parts.append("<p><b>计算过程（引擎留痕）</b></p><ol>{}</ol>".format(items))
    detail = section["detail"]
    if detail:
        head = "".join("<th align=\"left\">{}</th>".format(_escape(item))
                       for item in detail["headers"])
        body = "".join(
            "<tr>{}</tr>".format(
                "".join("<td>{}</td>".format(_escape(cell)) for cell in row))
            for row in detail["rows"]
        )
        parts.append("<p><b>{}</b></p><table border=\"0\" cellspacing=\"0\" "
                     "cellpadding=\"4\"><tr>{}</tr>{}</table>".format(
                         _escape(detail["title"]), head, body))
    return "".join(parts)


def _basis_html(sections):
    # type: (dict) -> str
    if not sections["basis"]:
        return "<p>本情形无适用补偿条款。</p>"
    blocks = []
    for clause in sections["basis"]:
        points = "".join("<li>{}</li>".format(_escape(point)) for point in clause["points"])
        blocks.append(
            "<p><b>{}</b> {}</p><ul>{}</ul>".format(
                _escape(clause["citation"]), _escape(clause["title"]), points)
        )
    return "".join(blocks)


def build_window(data_dir=None):
    # type: (object) -> object
    """构造主窗口（不进入事件循环；offscreen 冒烟测试直接用本函数）。

    :raises lcc.errors.OptionalDependencyError: PySide6 缺失
    """
    QtCore, QtGui, QtWidgets = _import_qt()
    from .. import pipeline

    class MainWindow(QtWidgets.QMainWindow):
        """主窗口：输入表单 + 四类计算页签 + 参数库页签 + 报告页签。"""

        def __init__(self, resolved_data_dir=None):
            # type: (object) -> None
            QtWidgets.QMainWindow.__init__(self)
            self._data_dir = resolved_data_dir
            self._result = None
            self.setWindowTitle("劳动用工合规计算引擎 v{}".format(__version__))
            self.resize(1080, 760)

            self._fields = {}
            self._browsers = {}
            self._tabs = QtWidgets.QTabWidget()
            self.setCentralWidget(self._build_root())
            self._load_overview()

        # ---- 布局 --------------------------------------------------
        def _build_root(self):
            # type: () -> object
            root = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(root)
            layout.addWidget(self._build_form())
            self._status = QtWidgets.QLabel("就绪")
            layout.addWidget(self._status)
            layout.addWidget(self._tabs, 1)

            for key, label in _MODULE_TABS:
                browser = QtWidgets.QTextBrowser()
                self._browsers[key] = browser
                self._tabs.addTab(browser, label)
            self._params_browser = QtWidgets.QTextBrowser()
            self._tabs.addTab(self._params_browser, "参数库")
            self._report_browser = QtWidgets.QTextBrowser()
            self._tabs.addTab(self._report_browser, "报告")
            self._basis_browser = QtWidgets.QTextBrowser()
            self._tabs.addTab(self._basis_browser, "适用依据")
            return root

        def _pair(self, form, row, left, right):
            # type: (object, int, tuple, object) -> None
            """在 ``row`` 行放两组「标签文字 + 控件」（左用列 0/1，右用列 2/3）。

            ``left`` / ``right`` 为 ``(标签文字, 控件)``；``right`` 为 None 时只放左半。
            """
            left_label, left_widget = left
            form.addWidget(self._label(left_label), row, 0)
            form.addWidget(left_widget, row, 1)
            if right is None:
                return
            right_label, right_widget = right
            form.addWidget(self._label(right_label), row, 2)
            form.addWidget(right_widget, row, 3)

        def _label(self, text):
            # type: (str) -> object
            widget = QtWidgets.QLabel(text)
            widget.setMinimumWidth(140)
            widget.setWordWrap(False)
            return widget

        def _build_form(self):
            # type: () -> object
            box = QtWidgets.QGroupBox("输入事实（全部在本机计算，不上传任何数据）")
            form = QtWidgets.QGridLayout(box)
            form.setColumnStretch(1, 2)
            form.setColumnStretch(3, 2)

            self._region = QtWidgets.QComboBox()
            self._region.setEditable(True)
            self._region.setCurrentText(_DEFAULTS["region_code"])
            self._year = QtWidgets.QLineEdit(_DEFAULTS["year"])
            self._pair(form, 0, ("地区码", self._region), ("年度", self._year))

            self._hire = QtWidgets.QLineEdit(_DEFAULTS["hire_date"])
            self._terminate = QtWidgets.QLineEdit(_DEFAULTS["terminate_date"])
            self._pair(form, 1, ("用工之日", self._hire), ("离职/终止之日", self._terminate))

            self._wages = QtWidgets.QPlainTextEdit(_DEFAULTS["monthly_wages"])
            self._wages.setFixedHeight(64)
            form.addWidget(self._label("月工资序列（逗号分隔）"), 2, 0)
            form.addWidget(self._wages, 2, 1, 1, 3)

            self._work_system = QtWidgets.QComboBox()
            self._work_system.addItems(["standard", "comprehensive", "irregular"])
            self._service_years = QtWidgets.QLineEdit(_DEFAULTS["cumulative_service_years"])
            self._pair(form, 3, ("工时制度", self._work_system),
                       ("累计工作年限", self._service_years))

            self._taken = QtWidgets.QLineEdit(_DEFAULTS["annual_leave_taken_days"])
            self._signed = QtWidgets.QCheckBox("已订立书面劳动合同")
            self._signed.setChecked(True)
            self._pair(form, 4, ("当年度已安排年休假（天）", self._taken),
                       ("合同状态", self._signed))

            self._signed_date = QtWidgets.QLineEdit(_DEFAULTS["contract_signed_date"])
            self._ground = QtWidgets.QComboBox()
            self._ground.addItems([
                "mutual_agreement", "employee_fault_dismissal",
                "employer_unilateral_no_fault", "economic_layoff",
                "illegal_termination", "contract_expiry_employer_no_renewal",
                "employee_resignation_art38", "employee_resignation_voluntary",
            ])
            self._pair(form, 5, ("合同订立之日（可空）", self._signed_date),
                       ("解除情形", self._ground))

            self._notified = QtWidgets.QComboBox()
            self._notified.addItems(["（不填）", "true", "false"])
            self._overtime = QtWidgets.QPlainTextEdit(_DEFAULTS["overtime"])
            self._overtime.setFixedHeight(64)
            self._pair(form, 6, ("是否提前 30 日通知", self._notified),
                       ("加班明细（每行：日期, 小时）", self._overtime))

            buttons = QtWidgets.QHBoxLayout()
            compute = QtWidgets.QPushButton("计算")
            compute.clicked.connect(self.compute)
            reset = QtWidgets.QPushButton("重置为示例")
            reset.clicked.connect(self.reset_form)
            export_md = QtWidgets.QPushButton("导出 Markdown")
            export_md.clicked.connect(self.export_markdown)
            export_xlsx = QtWidgets.QPushButton("导出 XLSX")
            export_xlsx.clicked.connect(self.export_xlsx)
            for widget in (compute, reset, export_md, export_xlsx):
                buttons.addWidget(widget)
            buttons.addStretch(1)
            form.addLayout(buttons, 7, 0, 1, 4)
            return box

        # ---- 数据搬运（无判定：只读表单 → 原样组 dict） --------------
        def _raw_case(self):
            # type: () -> dict
            self._fields = {}
            employment = {
                "region_code": self._region.currentText().strip(),
                "year": self._year.text().strip(),
                "hire_date": self._hire.text().strip(),
                "work_system": self._work_system.currentText(),
                "cumulative_service_years": self._service_years.text().strip(),
                "contract_signed": self._signed.isChecked(),
                "annual_leave_taken_days": self._taken.text().strip(),
                "monthly_wages": [
                    item.strip()
                    for item in self._wages.toPlainText().replace("\n", ",").split(",")
                    if item.strip()
                ],
                "overtime": self._raw_overtime(),
            }
            terminate = self._terminate.text().strip()
            if terminate:
                employment["terminate_date"] = terminate
            signed_date = self._signed_date.text().strip()
            if signed_date:
                employment["contract_signed_date"] = signed_date

            ground = self._ground.currentText()
            termination = {"ground": ground}
            notified = self._notified.currentText()
            if notified == "true":
                termination["notified_30d_in_advance"] = True
            elif notified == "false":
                termination["notified_30d_in_advance"] = False
            return {"employment": employment, "termination": termination}

        def _raw_overtime(self):
            # type: () -> list
            rows = []
            for line in self._overtime.toPlainText().splitlines():
                text = line.strip()
                if not text:
                    continue
                parts = [item.strip() for item in text.split(",") if item.strip()]
                if len(parts) >= 2:
                    rows.append({"date": parts[0], "hours": parts[1]})
            return rows

        # ---- 动作 --------------------------------------------------
        def reset_form(self):
            # type: () -> None
            self._region.setCurrentText(_DEFAULTS["region_code"])
            self._year.setText(_DEFAULTS["year"])
            self._hire.setText(_DEFAULTS["hire_date"])
            self._terminate.setText(_DEFAULTS["terminate_date"])
            self._wages.setPlainText(_DEFAULTS["monthly_wages"])
            self._work_system.setCurrentText(_DEFAULTS["work_system"])
            self._service_years.setText(_DEFAULTS["cumulative_service_years"])
            self._taken.setText(_DEFAULTS["annual_leave_taken_days"])
            self._signed.setChecked(True)
            self._signed_date.setText(_DEFAULTS["contract_signed_date"])
            self._ground.setCurrentText(_DEFAULTS["ground"])
            self._notified.setCurrentText(_DEFAULTS["notified_30d_in_advance"])
            self._overtime.setPlainText(_DEFAULTS["overtime"])
            self._status.setText("已重置为示例输入")

        def compute(self):
            # type: () -> object
            """走 CLI 同一条编排通路（pipeline）；失败时把异常展示在状态栏与报告页。"""
            try:
                case = pipeline.build_case(self._raw_case())
                request = pipeline.build_request(case, data_dir=self._data_dir)
                self._result = pipeline.compute_full_calc(request)
            except LccError as exc:
                self._result = None
                self._status.setText("计算未通过：{}".format(exc.message))
                for browser in self._browsers.values():
                    browser.setHtml("<p>{}</p>".format(_escape(exc.render())))
                self._report_browser.setHtml("<p>{}</p>".format(_escape(exc.render())))
                return None

            self._render_result()
            self._status.setText("计算完成：坐标 {} / {} 年".format(
                self._result.coordinate[0], self._result.coordinate[1]))
            return self._result

        def _render_result(self):
            # type: () -> None
            from ..report import render_markdown, report_sections

            sections = report_sections(self._result)
            by_name = {item["name"]: item for item in sections["modules"]}
            for key, label in _MODULE_TABS:
                section = by_name.get(key)
                browser = self._browsers[key]
                if section is None:
                    browser.setHtml("<p>（未产出该模块结论）</p>")
                else:
                    browser.setHtml(_module_html(section))
            self._basis_browser.setHtml(_basis_html(sections))
            self._report_browser.setHtml(
                "<p>以下为可导出的测算说明（Markdown 与 XLSX 同源）。</p>"
                "<pre>{}</pre>".format(_escape(render_markdown(self._result))))

        def export_markdown(self):
            # type: () -> object
            return self._export(".md")

        def export_xlsx(self):
            # type: () -> object
            return self._export(".xlsx")

        def _export(self, suffix):
            # type: (str) -> object
            if self._result is None:
                self._status.setText("请先点「计算」，再导出报告")
                return None
            from ..report import write_report

            path, _selected = QtWidgets.QFileDialog.getSaveFileName(
                self, "导出测算说明", "测算说明{}".format(suffix),
                "Markdown (*.md);;Excel (*.xlsx)")
            if not path:
                return None
            try:
                write_report(self._result, path)
            except LccError as exc:
                self._status.setText("导出失败：{}".format(exc.message))
                return None
            self._status.setText("已导出：{}".format(path))
            return path

        # ---- 参数库 / 条款库概览 ------------------------------------
        def _load_overview(self):
            # type: () -> None
            try:
                summary = pipeline.parameter_overview(self._data_dir)
                clauses = pipeline.clause_overview(self._data_dir)
            except (LccError, FileNotFoundError) as exc:
                self._params_browser.setHtml("<p>{}</p>".format(_escape(exc)))
                return
            self._params_browser.setHtml(_overview_html(summary, clauses))
            codes = [item["code"] for item in summary["regions"] if item["status"] == "verified"]
            for code in codes:
                if self._region.findText(code) < 0:
                    self._region.addItem(code)
            self._region.setCurrentText(_DEFAULTS["region_code"])

    return MainWindow(data_dir)


def _overview_html(summary, clauses):
    # type: (dict, list) -> str
    """参数库 + 条款库概览 HTML（渲染 pipeline 给出的数据，不做判定）。"""
    parts = ["<h3>数据目录</h3><p>{}</p>".format(_escape(summary["data_dir"]))]
    parts.append("<h3>地区主数据</h3><table><tr><th align=\"left\">地区码</th>"
                 "<th align=\"left\">名称</th><th align=\"left\">社平工资口径</th>"
                 "<th align=\"left\">状态</th></tr>")
    for item in summary["regions"]:
        parts.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            _escape(item["code"]), _escape(item["name"]),
            _escape(item["caliber"]), _escape(item["status"])))
    parts.append("</table>")
    parts.append("<h3>规则包（地区 × 年度）</h3><table><tr><th align=\"left\">坐标</th>"
                 "<th align=\"left\">名称</th><th align=\"left\">状态</th></tr>")
    for item in summary["rulesets"]:
        parts.append("<tr><td>{} / {}</td><td>{}</td><td>{}</td></tr>".format(
            _escape(item["region_code"]), _escape(item["year"]),
            _escape(item["region_name"]), _escape(item["status"])))
    parts.append("</table>")
    parts.append("<p>提示：status=pending 的参数包不得进入计算路径（门控拒绝）。</p>")
    parts.append("<h3>条款库（{} 条）</h3><ul>".format(len(clauses)))
    for clause in clauses:
        parts.append("<li><b>{}</b> {}</li>".format(
            _escape(clause["citation"]), _escape(clause["title"])))
    parts.append("</ul>")
    return "".join(parts)


def run(data_dir=None):
    # type: (object) -> int
    """启动桌面界面并进入事件循环；返回 CLI 退出码（0 成功 / 2 依赖缺失）。"""
    try:
        QtCore, QtGui, QtWidgets = _import_qt()
    except OptionalDependencyError as exc:
        for line in exc.render().splitlines():
            print(line)
        return EXIT_INPUT_ERROR

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = build_window(data_dir)
    icon = window.windowIcon()
    if icon.isNull():
        window.setWindowIcon(QtGui.QIcon())
    window.show()
    QtCore.QTimer.singleShot(0, window.compute)
    app.exec()
    return EXIT_OK


__all__ = ["MILESTONE", "build_window", "run"]
