"""编排层（plan/03 §四）：唯一编排源，CLI 与 GUI 共用（D-13）。

职责边界：
  * 解析输入 → 校验（:mod:`lcc.model`）
  * 按坐标加载参数包（:mod:`lcc.params`）→ 门控（:mod:`lcc.gate`）
  * 调用引擎（:mod:`lcc.engine.*`）
  * 汇总依据（:mod:`lcc.law`）并组装 :class:`CalcResult`

**零 Qt、零 IO 副作用**（除显式传入的路径读取）；判定逻辑一律不下沉到本层。

表现层（CLI / GUI）只经本模块的公开函数取数与行事：
:func:`build_request` / :func:`compute_full_calc` / :func:`parameter_overview` /
:func:`clause_overview` / :func:`module_label`。**GUI 不得直接 import 引擎、
参数库或门控模块**（M5-2 的 AST 守门断言），否则同一编排会出现两条实现。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import data_paths
from . import law as law_module
from . import params as params_module
from .engine import annual_leave as annual_leave_engine
from .engine import double_wage as double_wage_engine
from .engine import overtime as overtime_engine
from .engine import severance as severance_engine
from .errors import LccError, NotImplementedYet
from .gate import effective_ruleset
from .model import CaseInput

DISCLAIMER = (
    "免责声明：本测算结果仅供参考，不构成法律意见；正式结论以劳动仲裁/法院裁判为准。"
    "所有计算均在本地完成，不上传任何数据。"
)

MODULES = ("severance", "overtime", "annual_leave", "double_wage")

_MODULE_LABELS = {
    "severance": "经济补偿/赔偿金",
    "overtime": "加班费",
    "annual_leave": "未休年休假折算",
    "double_wage": "未签书面劳动合同二倍工资",
}


@dataclass
class CalcRequest(object):
    """计算请求：输入事实 + 计算模块选择。"""

    case: CaseInput
    modules: tuple = MODULES
    data_dir: object = None
    preview: bool = False

    @property
    def region_code(self):
        # type: () -> str
        return self.case.employment.region_code

    @property
    def year(self):
        # type: () -> int
        return self.case.employment.year


@dataclass
class CalcResult(object):
    """计算结果：输入事实 + 各模块结论 + 参数来源 + 依据条款 + 免责声明。

    ``case`` 为**原始输入事实**（:class:`lcc.model.CaseInput` 或 None）：报告与 GUI
    据此渲染「输入事实」段，调用方无需另行持有输入。它只是搬运，不含任何判定。
    """

    coordinate: tuple
    region_name: str = ""
    ruleset_status: str = ""
    case: object = None
    modules: dict = field(default_factory=dict)
    basis: list = field(default_factory=list)
    param_sources: dict = field(default_factory=dict)
    notices: list = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    preview: bool = False
    caliber: str = ""
    caliber_basis_year: object = None

    @property
    def has_amount(self):
        # type: () -> bool
        """是否产出了任何金额结论（预览模式一律为 False）。"""
        if self.preview:
            return False
        for payload in self.modules.values():
            if isinstance(payload, dict) and payload.get("amount") is not None:
                return True
        return False


def compute_full_calc(request):
    # type: (CalcRequest) -> CalcResult
    """执行一次完整计算。

    :raises lcc.errors.LccError: 各子类按其 ``exit_code`` 语义向上抛
    """
    case = request.case
    employment = case.employment

    ruleset = params_module.load_ruleset(
        employment.region_code, employment.year, data_dir=request.data_dir
    )
    constants = params_module.load_constants(data_dir=request.data_dir)
    effective = effective_ruleset(
        ruleset, constants, allow_pending=request.preview, data_dir=request.data_dir
    )

    result = CalcResult(
        coordinate=effective.coordinate,
        region_name=effective.region_name,
        ruleset_status=ruleset.status,
        case=case,
        preview=bool(request.preview),
    )

    if request.preview:
        result.notices.append(
            "预览模式：参数条目存在未核对（pending）项，仅展示参数元信息，不输出任何金额结论。"
        )

    result.param_sources = {
        "social_avg_wage_monthly": effective.param_source("social_avg_wage_monthly"),
        "min_wage_monthly": effective.param_source("min_wage_monthly"),
        "holiday_calendar": effective.param_source("holiday_calendar"),
    }
    result.caliber = effective.social_avg_wage_caliber()
    result.caliber_basis_year = effective.social_avg_wage_basis_year()

    basis_ids = []

    if request.preview:
        # 预览模式：门控命中时仅展示参数元信息，**不进入引擎**（plan/03 §131、
        # plan/04 §339：allow_pending 通路不得产出任何金额结论）。
        return result

    for name in request.modules:
        if name == "severance":
            if case.termination is None:
                result.notices.append("未提供 termination 段，跳过经济补偿/赔偿金计算。")
                continue
            payload = severance_engine.compute(employment, case.termination, effective)
        elif name == "overtime":
            payload = overtime_engine.compute(employment, effective)
        elif name == "annual_leave":
            payload = annual_leave_engine.compute(employment, effective)
        elif name == "double_wage":
            payload = double_wage_engine.compute(employment, effective)
        else:
            raise LccError("未知计算模块 {!r}".format(name))

        result.modules[name] = payload
        basis_ids.extend(list(payload.get("basis") or []))

    _attach_basis(result, basis_ids, request.data_dir)
    return result


def _attach_basis(result, basis_ids, data_dir):
    # type: (CalcResult, list, object) -> None
    """汇总依据条款（去重保序）；条款缺失时抛 LawBasisError（exit 1）。"""
    unique = []
    for clause_id in basis_ids:
        if clause_id not in unique:
            unique.append(clause_id)
    if not unique:
        result.basis = []
        return
    library = law_module.load_library(data_dir)
    result.basis = [clause.as_dict() for clause in library.resolve(unique)]


def module_label(name):
    # type: (str) -> str
    return _MODULE_LABELS.get(name, name)


def build_case(raw):
    # type: (dict) -> CaseInput
    """把原始输入 dict 校验为 :class:`lcc.model.CaseInput`。

    表现层（CLI / GUI）**不直接 import** :mod:`lcc.model`——输入校验也是编排的一部分，
    与请求构造一样收在本层，避免前端各自解释输入格式（D-13 编排上收）。
    """
    return CaseInput.from_dict(raw)


def build_request(case, modules=None, data_dir=None, preview=False):
    # type: (CaseInput, object, object, bool) -> CalcRequest
    """由校验后的输入事实构造计算请求（CLI 与 GUI 的共用入口）。

    ``modules`` 为 None 时取全部模块；这是**唯一**的请求构造点，避免两处
    各写一份默认值导致行为漂移。
    """
    if modules is None:
        modules = MODULES
    return CalcRequest(
        case=case,
        modules=tuple(modules),
        data_dir=data_dir,
        preview=bool(preview),
    )


def parameter_overview(data_dir=None):
    # type: (object) -> dict
    """参数库概览（坐标清单 + 核对状态 + 口径登记）。

    直接转发 :func:`lcc.params.summarize`：表现层（CLI `params` 子命令 / GUI 参数库
    页签）共用同一份数据，不得自行拼装。
    """
    return params_module.summarize(data_dir)


def clause_overview(data_dir=None):
    # type: (object) -> list
    """条款库概览（法律名 + 条号 + 要点），供依据页签与报告渲染。"""
    library = law_module.load_library(data_dir)
    return [clause.as_dict() for clause in library.clauses()]


def diagnostics(data_dir=None):
    # type: (object) -> dict
    """环境与数据自检（CLI ``doctor`` 的数据源；表现层只做渲染）。

    返回结构化结果而非打印：CLI 与未来的"自检"页签共用同一份判定，不各自探测。
    """
    report = {
        "data_dir": None,
        "data_dir_error": None,
        "library_count": None,
        "library_pending": None,
        "library_error": None,
        "constants_status": None,
        "constants_count": 0,
        "constants_error": None,
        "ruleset_files": 0,
        "verified_rulesets": 0,
        "ruleset_errors": [],
    }

    try:
        root = data_paths.find_data_dir(data_dir)
    except FileNotFoundError as exc:
        report["data_dir_error"] = str(exc)
        return report
    report["data_dir"] = root

    try:
        library = law_module.load_library(root)
        report["library_count"] = len(library.ids())
        report["library_pending"] = len(library.pending_ids())
    except LccError as exc:
        report["library_error"] = exc.message

    try:
        constants = params_module.load_constants(root)
        report["constants_status"] = constants.status
        report["constants_count"] = len(constants.entries())
    except LccError as exc:
        report["constants_error"] = exc.message

    files = params_module.list_ruleset_files(root)
    report["ruleset_files"] = len(files)
    for path in files:
        match = params_module.RULES_FILENAME_RE.match(os.path.basename(path))
        try:
            ruleset = params_module.load_ruleset(
                match.group("region"), match.group("year"), data_dir=root
            )
        except LccError as exc:
            report["ruleset_errors"].append((os.path.basename(path), exc.message))
            continue
        if ruleset.status == "verified":
            report["verified_rulesets"] += 1
    return report


def caliber_label(caliber):
    # type: (object) -> str
    """社平工资口径代码 → 人类可读标签（未知代码原样返回）。"""
    return _CALIBER_LABELS.get(str(caliber or ""), str(caliber or ""))


_CALIBER_LABELS = {
    "full_caliber_urban_employees": "全口径城镇单位就业人员平均工资",
    "urban_non_private_on_post": "城镇非私营单位在岗职工平均工资",
    "pending_caliber_registration": "（口径待核对登记）",
}


__all__ = [
    "DISCLAIMER",
    "MODULES",
    "CalcRequest",
    "CalcResult",
    "build_case",
    "build_request",
    "compute_full_calc",
    "module_label",
    "parameter_overview",
    "clause_overview",
    "diagnostics",
    "caliber_label",
    "NotImplementedYet",
]