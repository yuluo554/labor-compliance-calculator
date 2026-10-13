"""编排层（plan/03 §四）：唯一编排源，CLI 与 GUI 共用（D-13）。

职责边界：
  * 解析输入 → 校验（:mod:`lcc.model`）
  * 按坐标加载参数包（:mod:`lcc.params`）→ 门控（:mod:`lcc.gate`）
  * 调用引擎（:mod:`lcc.engine.*`）
  * 汇总依据（:mod:`lcc.law`）并组装 :class:`CalcResult`

**零 Qt、零 IO 副作用**（除显式传入的路径读取）；判定逻辑一律不下沉到本层。
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    """计算结果：各模块结论 + 参数来源 + 依据条款 + 免责声明。"""

    coordinate: tuple
    region_name: str = ""
    ruleset_status: str = ""
    modules: dict = field(default_factory=dict)
    basis: list = field(default_factory=list)
    param_sources: dict = field(default_factory=dict)
    notices: list = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    preview: bool = False

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

    basis_ids = []

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


__all__ = [
    "DISCLAIMER",
    "MODULES",
    "CalcRequest",
    "CalcResult",
    "compute_full_calc",
    "module_label",
    "NotImplementedYet",
]