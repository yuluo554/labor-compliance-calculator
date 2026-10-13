"""status 门控（单点）与「可计算规则集」。

纪律（plan/04 §7.1，FR-1.6）：**只有本模块能产出可计算的规则集**。
引擎函数签名只接受 :class:`EffectiveRuleset`，不接受裸 ``dict``/``Ruleset``
——从类型层面杜绝绕过门控。

``pending``（未核对）条目一旦进入计算路径即 :class:`GateError`；
``allow_pending=True`` 仅供 CLI ``--preview`` 预览参数元信息，
**调用方不得据此输出任何金额结论**。
"""

from __future__ import annotations

from decimal import Decimal

from .decimalutil import to_decimal
from .errors import GateError, ParamSchemaError
from .params import STATUS_PENDING, Constants, Ruleset

_PENDING_HINT = (
    "参数条目尚未核对（status=pending），按「未挂原文核对不得进入计算路径」纪律拒绝计算。"
    "请先按 data/README.md 台账逐条核对官方原文并置 status=verified。"
)


def pending_entries(ruleset, constants=None):
    # type: (Ruleset, object) -> list
    """列出全部未核对条目路径（规则包 + 常数包）。"""
    pending = []
    for path, entry in sorted(ruleset.entries().items()):
        if entry.status == STATUS_PENDING:
            pending.append("ruleset.{}".format(path))
    if constants is not None:
        for path, entry in sorted(constants.entries().items()):
            if entry.status == STATUS_PENDING:
                pending.append("constants.{}".format(path))
    return pending


class EffectiveRuleset(object):
    """门控通过后的可计算规则集：``地区 × 年度`` 参数 + 全国法定常数。

    引擎只能通过本对象取数——所有法定数值的唯一来源。
    """

    __slots__ = ("_ruleset", "_constants", "_allow_pending")

    def __init__(self, ruleset, constants, allow_pending=False):
        # type: (Ruleset, Constants, bool) -> None
        self._ruleset = ruleset
        self._constants = constants
        self._allow_pending = bool(allow_pending)

    # ---- 坐标 ----------------------------------------------------------
    @property
    def region_code(self):
        # type: () -> str
        return self._ruleset.region_code

    @property
    def region_name(self):
        # type: () -> str
        return self._ruleset.region_name

    @property
    def year(self):
        # type: () -> int
        return self._ruleset.year

    @property
    def coordinate(self):
        # type: () -> tuple
        return (self.region_code, self.year)

    @property
    def allow_pending(self):
        # type: () -> bool
        return self._allow_pending

    # ---- 通用取值 ------------------------------------------------------
    def _param(self, name):
        # type: (str) -> object
        entry = self._ruleset.get(name)
        if entry.status == STATUS_PENDING and not self._allow_pending:
            raise GateError("参数 {} 未核对（pending）".format(entry.path), [_PENDING_HINT])
        return entry.value()

    def _const(self, path):
        # type: (str) -> object
        entry = self._constants.get(path)
        if entry.status == STATUS_PENDING and not self._allow_pending:
            raise GateError("常数 {} 未核对（pending）".format(entry.path), [_PENDING_HINT])
        return entry.value()

    def _const_entry(self, path):
        # type: (str) -> object
        entry = self._constants.get(path)
        if entry.status == STATUS_PENDING and not self._allow_pending:
            raise GateError("常数 {} 未核对（pending）".format(entry.path), [_PENDING_HINT])
        return entry

    # ---- 地区参数（规则包） --------------------------------------------
    def social_avg_wage_monthly(self):
        # type: () -> Decimal
        return to_decimal(self._param("social_avg_wage_monthly"), "social_avg_wage_monthly")

    def social_avg_wage_caliber(self):
        # type: () -> str
        return str(self._ruleset.get("social_avg_wage_monthly").raw.get("caliber", ""))

    def social_avg_wage_basis_year(self):
        # type: () -> object
        return self._ruleset.get("social_avg_wage_monthly").raw.get("basis_year")

    def min_wage_monthly(self):
        # type: () -> Decimal
        return to_decimal(self._param("min_wage_monthly"), "min_wage_monthly")

    def holiday_days(self):
        # type: () -> list
        entry = self._ruleset.get("holiday_calendar")
        if entry.status == STATUS_PENDING and not self._allow_pending:
            raise GateError("参数 {} 未核对（pending）".format(entry.path), [_PENDING_HINT])
        return self._ruleset.holiday_days()

    def rest_days(self):
        # type: () -> list
        entry = self._ruleset.get("holiday_calendar")
        if entry.status == STATUS_PENDING and not self._allow_pending:
            raise GateError("参数 {} 未核对（pending）".format(entry.path), [_PENDING_HINT])
        return self._ruleset.rest_days()

    def adjusted_workdays(self):
        # type: () -> list
        entry = self._ruleset.get("holiday_calendar")
        if entry.status == STATUS_PENDING and not self._allow_pending:
            raise GateError("参数 {} 未核对（pending）".format(entry.path), [_PENDING_HINT])
        return self._ruleset.adjusted_workdays()

    def holiday_day_type(self, day):
        # type: (str) -> str
        """日期 → ``statutory_holiday`` / ``rest_day`` / ``adjusted_workday`` / ``workday``。

        日历是判定日期类型的**唯一来源**（plan/04 §4.3）：引擎不得自建日历逻辑，
        否则政策语义会出现第二份实现。
        """
        entry = self._ruleset.get("holiday_calendar")
        if entry.status == STATUS_PENDING and not self._allow_pending:
            raise GateError("参数 {} 未核对（pending）".format(entry.path), [_PENDING_HINT])
        return self._ruleset.holiday_day_type(day)

    def param_source(self, name):
        # type: (str) -> dict
        """参数来源登记（报告「参数来源块」用）。"""
        return self._ruleset.get(name).source

    # ---- 法定常数（经济补偿） ------------------------------------------
    def severance_cap_multiple(self):
        # type: () -> Decimal
        return to_decimal(self._const("severance.cap_multiple_of_social_avg"),
                          "severance.cap_multiple_of_social_avg")

    def severance_cap_years(self):
        # type: () -> Decimal
        return to_decimal(self._const("severance.cap_years"), "severance.cap_years")

    def avg_wage_months(self):
        # type: () -> Decimal
        return to_decimal(self._const("severance.avg_wage_months"), "severance.avg_wage_months")

    def full_year_threshold_months(self):
        # type: () -> Decimal
        return to_decimal(self._const("severance.rounding.full_year_threshold_months"),
                          "severance.rounding.full_year_threshold_months")

    def round_up_to_year(self):
        # type: () -> Decimal
        return to_decimal(self._const("severance.rounding.round_up_to_year"),
                          "severance.rounding.round_up_to_year")

    def round_down_to_half_month(self):
        # type: () -> Decimal
        return to_decimal(self._const("severance.rounding.round_down_to_half_month"),
                          "severance.rounding.round_down_to_half_month")

    def compensation_multiple(self):
        # type: () -> Decimal
        """违法解除赔偿金倍数（2N 的 2）。"""
        return to_decimal(self._const("severance.compensation_multiple"),
                          "severance.compensation_multiple")

    def severance_basis(self):
        # type: () -> list
        return self._const_entry("severance.cap_years").basis

    # ---- 法定常数（加班费） --------------------------------------------
    def overtime_rate(self, kind):
        # type: (str) -> Decimal
        return to_decimal(self._const("overtime.rates.{}".format(kind)),
                          "overtime.rates.{}".format(kind))

    def overtime_standard_daily_hours(self):
        # type: () -> Decimal
        return to_decimal(self._const("overtime.standard_daily_hours"),
                          "overtime.standard_daily_hours")

    def overtime_basis(self):
        # type: () -> list
        return self._const_entry("overtime.rates.workday_extension").basis

    # ---- 法定常数（年休假） --------------------------------------------
    def monthly_pay_days(self):
        # type: () -> Decimal
        return to_decimal(self._const("annual_leave.monthly_pay_days"),
                          "annual_leave.monthly_pay_days")

    def entitlement_tiers(self):
        # type: () -> list
        tiers = []
        raw = (self._constants.raw.get("constants") or {}).get("annual_leave") or {}
        for index, tier in enumerate(raw.get("entitlement_tiers") or []):
            self._const_entry("annual_leave.entitlement_tiers[{}]".format(index))
            tiers.append(
                {
                    "min_service_years": to_decimal(tier.get("min_service_years"),
                                                    "min_service_years"),
                    "max_service_years_exclusive": (
                        None if tier.get("max_service_years_exclusive") is None
                        else to_decimal(tier.get("max_service_years_exclusive"),
                                        "max_service_years_exclusive")
                    ),
                    "days": to_decimal(tier.get("days"), "days"),
                    "basis": list(tier.get("basis") or []),
                }
            )
        if not tiers:
            raise ParamSchemaError("常数包缺少 annual_leave.entitlement_tiers")
        return tiers

    def unused_multiple(self):
        # type: () -> Decimal
        return to_decimal(self._const("annual_leave.unused_multiple"),
                          "annual_leave.unused_multiple")

    def already_paid_portion(self):
        # type: () -> Decimal
        return to_decimal(self._const("annual_leave.already_paid_portion"),
                          "annual_leave.already_paid_portion")

    def days_per_year(self):
        # type: () -> Decimal
        return to_decimal(self._const("annual_leave.days_per_year"),
                          "annual_leave.days_per_year")

    def annual_leave_basis(self):
        # type: () -> list
        return self._const_entry("annual_leave.unused_multiple").basis

    # ---- 法定常数（二倍工资） ------------------------------------------
    def double_wage_start_after_months(self):
        # type: () -> Decimal
        return to_decimal(self._const("double_wage.start_after_months"),
                          "double_wage.start_after_months")

    def double_wage_max_months(self):
        # type: () -> Decimal
        return to_decimal(self._const("double_wage.max_months"), "double_wage.max_months")

    def double_wage_difference_multiple(self):
        # type: () -> Decimal
        """二倍工资**差额**倍数（已付一倍，另付差额 = 1 倍月工资）。"""
        return to_decimal(self._const("double_wage.difference_multiple"),
                          "double_wage.difference_multiple")

    def double_wage_basis(self):
        # type: () -> list
        return self._const_entry("double_wage.max_months").basis

    def __repr__(self):
        # type: () -> str
        return "EffectiveRuleset(region={!r}, year={}, allow_pending={})".format(
            self.region_code, self.year, self._allow_pending
        )


def effective_ruleset(ruleset, constants=None, allow_pending=False, data_dir=None):
    # type: (Ruleset, object, bool, object) -> EffectiveRuleset
    """门控入口：产出可计算规则集。

    :param ruleset: 已加载的 ``地区 × 年度`` 参数包
    :param constants: 法定常数包（None 时自动加载）
    :param allow_pending: 仅预览用；**不得据此输出金额**
    :raises GateError: 命中未核对条目且 ``allow_pending=False``
    """
    if constants is None:
        from .params import load_constants

        constants = load_constants(data_dir)

    if not allow_pending:
        pending = pending_entries(ruleset, constants)
        if pending:
            raise GateError(
                "门控拦截：{} 个条目尚未核对（pending），不得进入计算路径".format(len(pending)),
                pending + [_PENDING_HINT],
            )
    return EffectiveRuleset(ruleset, constants, allow_pending=allow_pending)


__all__ = ["EffectiveRuleset", "effective_ruleset", "pending_entries"]