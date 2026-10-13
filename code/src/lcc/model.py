"""输入事实模型（plan/04 §2）。

所有金额/天数在进入引擎前已 Decimal 化；校验失败一律 :class:`InputError`
（CLI exit 2）。模型为不可变 dataclass，避免引擎误改输入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .decimalutil import to_decimal
from .errors import InputError

# 工时制度枚举（plan/04 §4.1）
WORK_SYSTEMS = ("standard", "comprehensive", "irregular")

# 解除情形枚举（plan/04 §3.1）
TERMINATION_GROUNDS = (
    "mutual_agreement",                      # 第 36 条 协商一致
    "employee_fault_dismissal",              # 第 39 条 劳动者过错
    "employer_unilateral_no_fault",          # 第 40 条 无过失性辞退（是否提前通知见 notified_30d）
    "economic_layoff",                       # 第 41 条 经济性裁员
    "illegal_termination",                   # 第 48/87 条 违法解除
    "contract_expiry_employer_no_renewal",   # 第 46 条第 5 项 到期不续订
    "employee_resignation_art38",            # 第 38 条 被迫解除
    "employee_resignation_voluntary",        # 劳动者主动辞职
)

# 加班类型
OVERTIME_KINDS = ("workday_extension", "rest_day", "statutory_holiday")


def parse_date(value, field_name="date"):
    # type: (object, str) -> date
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise InputError("{}: 日期为空".format(field_name))
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise InputError("{}: 日期格式非法 {!r}（应为 YYYY-MM-DD）".format(field_name, value))
    raise InputError("{}: 不支持的日期类型 {}".format(field_name, type(value).__name__))


@dataclass(frozen=True)
class OvertimeEntry:
    """单条加班明细。"""

    date: date
    hours: Decimal
    kind: str = "auto"  # auto = 由节假日日历判定；否则显式指定

    @staticmethod
    def from_dict(raw, index=0):
        # type: (dict, int) -> OvertimeEntry
        if not isinstance(raw, dict):
            raise InputError("overtime[{}]: 应为对象".format(index))
        kind = str(raw.get("kind", "auto"))
        if kind != "auto" and kind not in OVERTIME_KINDS:
            raise InputError(
                "overtime[{}]: kind 非法 {!r}，应为 auto 或 {}".format(
                    index, kind, "/".join(OVERTIME_KINDS))
            )
        hours = to_decimal(raw.get("hours", 0), "overtime[{}].hours".format(index))
        if hours < 0:
            raise InputError("overtime[{}].hours 不得为负".format(index))
        return OvertimeEntry(
            date=parse_date(raw.get("date"), "overtime[{}].date".format(index)),
            hours=hours,
            kind=kind,
        )


@dataclass(frozen=True)
class EmploymentFacts:
    """雇佣事实（输入）。"""

    region_code: str
    year: int
    hire_date: date
    terminate_date: object = None
    monthly_wages: tuple = field(default_factory=tuple)
    work_system: str = "standard"
    cumulative_service_years: Decimal = Decimal(0)
    contract_signed: bool = True
    contract_signed_date: object = None
    overtime: tuple = field(default_factory=tuple)
    annual_leave_taken_days: Decimal = Decimal(0)

    @staticmethod
    def from_dict(raw):
        # type: (dict) -> EmploymentFacts
        if not isinstance(raw, dict):
            raise InputError("employment 事实应为对象")

        region_code = str(raw.get("region_code") or "").strip()
        if not region_code:
            raise InputError("employment.region_code 必填（地区×年度参数坐标）")

        try:
            year = int(raw.get("year"))
        except (TypeError, ValueError):
            raise InputError("employment.year 必填且为四位年度")

        hire_date = parse_date(raw.get("hire_date"), "employment.hire_date")
        terminate_date = None
        if raw.get("terminate_date"):
            terminate_date = parse_date(raw.get("terminate_date"), "employment.terminate_date")
            if terminate_date < hire_date:
                raise InputError("employment.terminate_date 早于 hire_date（日期区间倒置）")

        work_system = str(raw.get("work_system", "standard"))
        if work_system not in WORK_SYSTEMS:
            raise InputError(
                "employment.work_system 非法 {!r}，应为 {}".format(
                    work_system, "/".join(WORK_SYSTEMS))
            )

        wages = []
        for index, item in enumerate(raw.get("monthly_wages") or []):
            value = to_decimal(item, "employment.monthly_wages[{}]".format(index))
            if value < 0:
                raise InputError("employment.monthly_wages[{}] 不得为负".format(index))
            wages.append(value)

        service_years = to_decimal(
            raw.get("cumulative_service_years", 0), "employment.cumulative_service_years"
        )
        if service_years < 0:
            raise InputError("employment.cumulative_service_years 不得为负")

        taken = to_decimal(
            raw.get("annual_leave_taken_days", 0), "employment.annual_leave_taken_days"
        )
        if taken < 0:
            raise InputError("employment.annual_leave_taken_days 不得为负")

        contract_signed_date = None
        if raw.get("contract_signed_date"):
            contract_signed_date = parse_date(
                raw.get("contract_signed_date"), "employment.contract_signed_date"
            )

        overtime = tuple(
            OvertimeEntry.from_dict(item, index)
            for index, item in enumerate(raw.get("overtime") or [])
        )

        return EmploymentFacts(
            region_code=region_code,
            year=year,
            hire_date=hire_date,
            terminate_date=terminate_date,
            monthly_wages=tuple(wages),
            work_system=work_system,
            cumulative_service_years=service_years,
            contract_signed=bool(raw.get("contract_signed", True)),
            contract_signed_date=contract_signed_date,
            overtime=overtime,
            annual_leave_taken_days=taken,
        )


@dataclass(frozen=True)
class TerminationFacts:
    """解除事实（输入）。"""

    ground: str
    notified_30d_in_advance: object = None
    employee_fault: bool = False
    mutual_agreement: bool = False

    @staticmethod
    def from_dict(raw):
        # type: (dict) -> TerminationFacts
        if not isinstance(raw, dict):
            raise InputError("termination 事实应为对象")
        ground = str(raw.get("ground") or "").strip()
        if ground not in TERMINATION_GROUNDS:
            raise InputError(
                "termination.ground 非法 {!r}，应为 {}".format(
                    ground, " / ".join(TERMINATION_GROUNDS))
            )
        notified = raw.get("notified_30d_in_advance")
        if notified is not None:
            notified = bool(notified)
        return TerminationFacts(
            ground=ground,
            notified_30d_in_advance=notified,
            employee_fault=bool(raw.get("employee_fault", False)),
            mutual_agreement=bool(raw.get("mutual_agreement", False)),
        )


@dataclass(frozen=True)
class CaseInput:
    """一份完整输入：雇佣事实 + 解除事实（解除可缺省，用于只算加班费等场景）。"""

    employment: EmploymentFacts
    termination: object = None

    @staticmethod
    def from_dict(raw):
        # type: (dict) -> CaseInput
        if not isinstance(raw, dict):
            raise InputError("输入应为 JSON 对象")
        if "employment" not in raw:
            raise InputError("输入缺少 employment 段")
        termination = None
        if raw.get("termination"):
            termination = TerminationFacts.from_dict(raw["termination"])
        return CaseInput(
            employment=EmploymentFacts.from_dict(raw["employment"]),
            termination=termination,
        )


__all__ = [
    "WORK_SYSTEMS",
    "TERMINATION_GROUNDS",
    "OVERTIME_KINDS",
    "parse_date",
    "OvertimeEntry",
    "EmploymentFacts",
    "TerminationFacts",
    "CaseInput",
]