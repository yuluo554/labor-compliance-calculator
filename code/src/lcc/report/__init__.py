"""报告导出（Markdown + XLSX）——M5 实现（FR-6）。

纪律：
  * 报告内容 = :class:`lcc.pipeline.CalcResult` 的**渲染**，不新增任何判定；
  * 两种格式共用同一份「章节结构」（:func:`report_sections`）→ 内容天然一致
    （FR-6.1 的「两格式内容一致」不是靠人工比对，而是靠单一渲染源）；
  * 必须含：输入事实、适用法条、逐项计算过程、**参数来源块**（哪年哪地社平工资 +
    发布机关 + URL + 口径）、结论汇总、**免责声明**（FR-6.3）；
  * XLSX 为可选依赖（``openpyxl``，extra ``report``）——渲染在 :mod:`lcc.report.xlsx`
    （**唯一的可选依赖边界**），缺失时 :class:`~lcc.errors.OptionalDependencyError`
    （exit 1）并提示回退 Markdown：不崩溃、不静默产出半成品。

**本模块保持 stdlib-only**（零第三方依赖），与 :mod:`lcc.report.xlsx` 分工：
本模块产出章节结构与 Markdown；XLSX 由后者守卫式惰性导入 openpyxl。这样
「零依赖导出通路」（Markdown）与「可选依赖通路」（XLSX）在结构上分离。

**无判定逻辑**：只做取值与排版；「该不该封顶」「取整方向」之类由引擎在
:mod:`lcc.pipeline` 之下决定，报告层原样呈现引擎给出的数值与 ``steps``。
"""
from __future__ import annotations

import os
from decimal import Decimal

from ..errors import OptionalDependencyError
from ..pipeline import caliber_label, module_label

MILESTONE = "M5"

# 模块结果的字段呈现顺序与中文标签（纯排版元数据，不含任何判定）
_MODULE_FIELDS = {
    "severance": (
        ("formula", "口径"),
        ("reason", "判定说明"),
        ("service_years", "工作年限（取整后）"),
        ("monthly_wage_avg", "月平均应得工资（元）"),
        ("min_wage_applied", "最低工资下限是否生效"),
        ("cap_applied", "三倍封顶是否生效"),
        ("cap_base", "封顶基数（元）"),
        ("basis_wage", "实际计算基数（元）"),
        ("years_used", "计算年限（年）"),
        ("amount", "金额（元）"),
    ),
    "overtime": (
        ("hourly_base", "小时工资基数（元）"),
        ("min_wage_applied", "最低工资下限是否生效"),
        ("work_system", "工时制度（记录性字段）"),
        ("total", "加班费合计（元）"),
        ("amount", "金额（元）"),
    ),
    "annual_leave": (
        ("entitlement_days", "年度应休天数（天）"),
        ("prorated_days", "当年度折算应休天数（天，保留原值）"),
        ("taken_days", "当年度已安排天数（天）"),
        ("unused_days", "应休未休天数（天，向下取整）"),
        ("monthly_wage", "月平均应得工资（元）"),
        ("daily_wage", "日工资（元）"),
        ("payable_total", "未休年休假工资报酬（含已付部分，元）"),
        ("already_paid", "其中已付部分（元）"),
        ("additional_due", "另付部分（元）"),
        ("amount", "金额（元）"),
    ),
    "double_wage": (
        ("signed", "是否已订立书面劳动合同"),
        ("start_date", "起算日"),
        ("end_date", "截止日"),
        ("months", "区间月数（首尾含当月）"),
        ("monthly_wage", "月工资基数（元）"),
        ("total_difference", "二倍工资差额合计（元）"),
        ("amount", "金额（元）"),
    ),
}

_DETAIL_TABLES = {
    "overtime": (
        "加班逐条明细",
        ("date", "day_type", "rate", "hours", "entry_amount"),
        ("日期", "日期类型", "倍率", "小时数", "该条金额（元）"),
    ),
    "double_wage": (
        "二倍工资逐月明细",
        ("month", "due", "paid", "difference"),
        ("月份", "应付（元）", "已付（元）", "差额（元）"),
    ),
}

_DAY_TYPE_LABELS = {
    "statutory_holiday": "法定节假日",
    "rest_day": "休息日",
    "adjusted_workday": "调休上班日",
    "workday": "普通工作日",
}

_PARAM_LABELS = {
    "social_avg_wage_monthly": "社会平均工资（月，三倍封顶基数来源）",
    "min_wage_monthly": "最低工资标准（月）",
    "holiday_calendar": "法定节假日日历（含调休）",
}


# --------------------------------------------------------------------------
# 取值与格式化（纯排版）
# --------------------------------------------------------------------------

def _text(value):
    # type: (object) -> str
    """任意值 → 展示串（Decimal 原样、布尔中文、None 占位）。"""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "、".join(_text(item) for item in value) if value else "—"
    return str(value)


def _day_type_label(day_type):
    # type: (object) -> str
    return _DAY_TYPE_LABELS.get(str(day_type or ""), _text(day_type))


def _case_lines(result):
    # type: (object) -> list
    """输入事实 → ``[(标签, 值)]``（原样搬运，不解释）。"""
    case = getattr(result, "case", None)
    employment = getattr(case, "employment", None)
    termination = getattr(case, "termination", None)
    if employment is None:
        return []

    lines = [
        ("地区（坐标）", "{} {}".format(
            result.coordinate[0], result.region_name or "（未登记名称）")),
        ("年度（坐标）", str(result.coordinate[1])),
        ("用工之日", _text(employment.hire_date)),
        ("离职/终止之日", _text(employment.terminate_date)),
        ("工时制度", _text(employment.work_system)),
        ("累计工作年限", _text(employment.cumulative_service_years)),
        ("月工资序列（元）", "、".join(_text(item) for item in employment.monthly_wages) or "—"),
        ("是否订立书面劳动合同", _text(employment.contract_signed)),
        ("合同订立之日", _text(employment.contract_signed_date)),
        ("当年度已安排年休假（天）", _text(employment.annual_leave_taken_days)),
    ]
    overtime = getattr(employment, "overtime", ()) or ()
    if overtime:
        lines.append((
            "加班明细",
            "、".join("{} {} 小时".format(item.date, item.hours) for item in overtime),
        ))
    if termination is not None:
        lines.append(("解除情形", _text(termination.ground)))
        lines.append(("是否提前 30 日通知", _text(termination.notified_30d_in_advance)))
    return lines


def _source_line(source):
    # type: (dict) -> str
    """参数来源 → 单行「发布机关 + 年度 + 文号 + URL + 抓取日期」。"""
    source = dict(source or {})
    publisher = source.get("publisher") or "（未登记发布机关）"
    year = source.get("published_year")
    doc_no = source.get("doc_no")
    url = source.get("url") or "（未登记 URL）"
    retrieved = source.get("retrieved_at")
    parts = [str(publisher)]
    if year:
        parts.append("{} 年".format(year))
    if doc_no:
        parts.append(str(doc_no))
    parts.append(str(url))
    if retrieved:
        parts.append("抓取于 {}".format(retrieved))
    return " ｜ ".join(parts)


def report_sections(result):
    # type: (object) -> dict
    """把 :class:`~lcc.pipeline.CalcResult` 摊成章节结构（Markdown 与 XLSX 的唯一来源）。

    :returns: ``{"meta": [...], "inputs": [...], "params": [...], "modules": [...],
        "basis": [...], "notices": [...], "disclaimer": str, "preview": bool}``
        其中 ``modules`` 每项为 ``{"name", "label", "fields": [(标签, 值)],
        "steps": [str], "detail": {"title", "headers", "rows"} 或 None,
        "amount": str 或 None}``。
    """
    meta = [
        ("计算坐标", "{} / {} 年（{}）".format(
            result.coordinate[0], result.coordinate[1],
            result.region_name or "未登记名称")),
        ("规则包核对状态", result.ruleset_status or "—"),
        ("社平工资口径", caliber_label(result.caliber)),
        ("口径依据年度", _text(result.caliber_basis_year)),
    ]
    if result.preview:
        meta.append(("模式", "预览模式（仅参数元信息，不输出金额结论）"))

    params = []
    for name in ("social_avg_wage_monthly", "min_wage_monthly", "holiday_calendar"):
        source = result.param_sources.get(name)
        if source is None:
            continue
        params.append((_PARAM_LABELS.get(name, name), _source_line(source)))

    modules = []
    for name, payload in result.modules.items():
        if not isinstance(payload, dict):
            continue
        fields = []
        for key, label in _MODULE_FIELDS.get(name, ()):
            if key in payload:
                fields.append((label, _text(payload[key])))
        if not fields:
            # 未知模块：原样罗列标量字段，避免"报告漏掉结论"
            for key in sorted(payload):
                value = payload[key]
                if value is None or isinstance(value, (str, int, float, Decimal, bool)):
                    fields.append((key, _text(value)))

        detail = None
        spec = _DETAIL_TABLES.get(name)
        rows = payload.get("monthly_detail") if name == "double_wage" else payload.get("entries")
        if spec and rows:
            title, keys, headers = spec
            detail = {
                "title": title,
                "headers": list(headers),
                "rows": [
                    [_day_type_label(row.get(key)) if key == "day_type" else _text(row.get(key))
                     for key in keys]
                    for row in rows
                ],
            }

        amount = payload.get("amount")
        modules.append({
            "name": name,
            "label": module_label(name),
            "fields": fields,
            "steps": [_text(step) for step in (payload.get("steps") or [])],
            "detail": detail,
            "amount": None if amount is None else _text(amount),
        })

    basis = [
        {
            "citation": clause.get("citation", ""),
            "title": clause.get("title", ""),
            "points": list(clause.get("points") or []),
        }
        for clause in (result.basis or [])
    ]

    return {
        "meta": meta,
        "inputs": _case_lines(result),
        "params": params,
        "modules": modules,
        "basis": basis,
        "notices": [_text(item) for item in (result.notices or [])],
        "disclaimer": result.disclaimer,
        "preview": bool(result.preview),
    }


# --------------------------------------------------------------------------
# Markdown（stdlib-only）
# --------------------------------------------------------------------------

def _md_table(pairs):
    # type: (list) -> list
    lines = ["| 项目 | 内容 |", "|---|---|"]
    for label, value in pairs:
        lines.append("| {} | {} |".format(label, str(value).replace("|", "\\|")))
    return lines


def render_markdown(result):
    # type: (object) -> str
    """渲染 Markdown 测算说明（含免责声明与参数来源块）。"""
    sections = report_sections(result)
    lines = ["# 劳动用工合规测算说明", ""]

    lines.append("## 一、基本信息")
    lines.append("")
    lines.extend(_md_table(sections["meta"]))
    lines.append("")

    lines.append("## 二、输入事实")
    lines.append("")
    lines.extend(_md_table(sections["inputs"]) if sections["inputs"] else ["（未提供输入事实）"])
    lines.append("")

    lines.append("## 三、参数来源")
    lines.append("")
    lines.extend(_md_table(sections["params"]) if sections["params"] else ["（无参数来源登记）"])
    lines.append("")

    lines.append("## 四、逐项计算结果")
    lines.append("")
    if not sections["modules"]:
        lines.append("（无模块结论）")
    for module in sections["modules"]:
        lines.append("### {}".format(module["label"]))
        lines.append("")
        lines.extend(_md_table(module["fields"]) if module["fields"] else ["（无字段）"])
        lines.append("")
        if module["steps"]:
            lines.append("**计算过程（引擎留痕）**")
            lines.append("")
            for index, step in enumerate(module["steps"], 1):
                lines.append("{}. {}".format(index, step))
            lines.append("")
        detail = module["detail"]
        if detail:
            lines.append("**{}**".format(detail["title"]))
            lines.append("")
            lines.append("| {} |".format(" | ".join(detail["headers"])))
            lines.append("|{}|".format("---|" * len(detail["headers"])))
            for row in detail["rows"]:
                lines.append("| {} |".format(" | ".join(row)))
            lines.append("")

    lines.append("## 五、适用依据")
    lines.append("")
    if sections["basis"]:
        for clause in sections["basis"]:
            lines.append("- **{}** {}".format(clause["citation"], clause["title"]))
            for point in clause["points"]:
                lines.append("  - {}".format(point))
    else:
        lines.append("（本情形无适用补偿条款）")
    lines.append("")

    if sections["notices"]:
        lines.append("## 六、说明")
        lines.append("")
        for notice in sections["notices"]:
            lines.append("- {}".format(notice))
        lines.append("")

    lines.append("## 免责声明")
    lines.append("")
    lines.append(sections["disclaimer"])
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 导出入口
# --------------------------------------------------------------------------

def render_xlsx(result, path, sections=None):
    # type: (object, str, object) -> str
    """XLSX 渲染的**委托入口**（真实实现在 :mod:`lcc.report.xlsx`）。

    保留本函数名以维持 ``report.render_xlsx`` 的既有调用面；可选依赖的守卫式导入
    与渲染全部在子模块内，本模块因此保持 stdlib-only。
    """
    from .xlsx import render_xlsx as _render_xlsx

    return _render_xlsx(result, path, sections=sections)


def write_report(result, path):
    # type: (object, str) -> str
    """按扩展名导出报告：``.md`` → Markdown；``.xlsx`` → XLSX。返回写入路径。"""
    suffix = os.path.splitext(str(path))[1].lower()
    if suffix in (".md", ".markdown"):
        text = render_markdown(result)
        directory = os.path.dirname(os.path.abspath(path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path
    if suffix in (".xlsx", ".xlsm"):
        return render_xlsx(result, path)
    raise OptionalDependencyError(
        "不支持的报告扩展名 {!r}".format(suffix), ["请使用 .md 或 .xlsx。"]
    )


__all__ = [
    "MILESTONE",
    "report_sections",
    "render_markdown",
    "render_xlsx",
    "write_report",
]
