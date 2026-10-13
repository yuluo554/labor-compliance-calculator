"""参数库：地区主数据、地区×年度规则包、全国法定常数包。

设计要点（plan/04 §1）：
  * **坐标精确匹配**：``load_ruleset(region_code, year)`` 只按精确坐标命中，不做
    模糊/回退匹配；文件名 ``ruleset-<region>-<year>.json`` 必须与内部
    ``region_code`` / ``year`` 一致，否则 :class:`ParamSchemaError`。
    → 跨地区/跨年度混用在机制上不可能发生（FR-1.4）。
  * **来源纪律**：``status == "verified"`` 的条目必须挂齐来源字段，否则
    :class:`ParamSchemaError`（FR-1.3）。初始化数据全部 ``pending``。
  * 本模块**不做**门控放行判定——那是 :mod:`lcc.gate` 的职责（单点）。
"""

from __future__ import annotations

import os
import re

from .data_paths import find_data_dir
from .decimalutil import load_json_decimal, to_decimal
from .errors import ParamCoordinateError, ParamSchemaError

RULES_FILENAME_RE = re.compile(r"^ruleset-(?P<region>[0-9A-Za-z]+)-(?P<year>\d{4})\.json$")

STATUS_PENDING = "pending"
STATUS_VERIFIED = "verified"
_VALID_STATUS = (STATUS_PENDING, STATUS_VERIFIED)

# verified 的地区参数条目必须齐备的来源字段
REQUIRED_SOURCE_KEYS = ("publisher", "published_year", "url", "retrieved_at")


class ParamEntry(object):
    """单个参数条目：值 + 单位 + 状态 + 来源（+ 口径等附加字段）。"""

    __slots__ = ("path", "raw")

    def __init__(self, path, raw):
        # type: (str, dict) -> None
        self.path = path
        self.raw = raw

    @property
    def status(self):
        # type: () -> str
        return str(self.raw.get("status", STATUS_PENDING))

    @property
    def is_verified(self):
        # type: () -> bool
        return self.status == STATUS_VERIFIED

    @property
    def unit(self):
        # type: () -> object
        return self.raw.get("unit")

    @property
    def source(self):
        # type: () -> dict
        return dict(self.raw.get("source") or {})

    @property
    def basis(self):
        # type: () -> list
        return list(self.raw.get("basis") or [])

    def value(self):
        # type: () -> object
        """返回 Decimal（数值型）或原始值（列表/字典/布尔/字符串）。"""
        raw = self.raw.get("value")
        if isinstance(raw, (list, dict, bool)):
            return raw
        return to_decimal(raw, self.path)

    def __repr__(self):
        # type: () -> str
        return "ParamEntry(path={!r}, status={!r})".format(self.path, self.status)


class Ruleset(object):
    """一份 ``地区 × 年度`` 参数包。"""

    def __init__(self, raw, source_file=None):
        # type: (dict, object) -> None
        self.raw = raw
        self.source_file = source_file

    @property
    def region_code(self):
        # type: () -> str
        return str(self.raw.get("region_code", ""))

    @property
    def region_name(self):
        # type: () -> str
        return str(self.raw.get("region_name", ""))

    @property
    def year(self):
        # type: () -> int
        return int(self.raw.get("year", 0))

    @property
    def status(self):
        # type: () -> str
        """整包状态：子项有 pending 则整包 pending（取最严）。"""
        declared = str(self.raw.get("status", STATUS_PENDING))
        if declared != STATUS_VERIFIED:
            return STATUS_PENDING
        for entry in self.entries().values():
            if not entry.is_verified:
                return STATUS_PENDING
        return STATUS_VERIFIED

    @property
    def coordinate(self):
        # type: () -> tuple
        return (self.region_code, self.year)

    def entries(self):
        # type: () -> dict
        """全部参数条目：``{"params.social_avg_wage_monthly": ParamEntry, ...}``。"""
        result = {}
        for name, raw in (self.raw.get("params") or {}).items():
            path = "params.{}".format(name)
            if isinstance(raw, dict) and "status" in raw:
                result[path] = ParamEntry(path, raw)
            elif isinstance(raw, dict):
                # 复合条目（如 holiday_calendar 含 days/adjusted_workdays）
                result[path] = ParamEntry(path, raw)
        return result

    def get(self, name):
        # type: (str) -> ParamEntry
        entries = self.entries()
        key = "params.{}".format(name)
        if key not in entries:
            raise ParamSchemaError("参数包 {} 缺少条目 {}".format(self.coordinate, key))
        return entries[key]

    def holiday_days(self):
        # type: () -> list
        calendar = (self.raw.get("params") or {}).get("holiday_calendar") or {}
        return list(calendar.get("days") or [])

    def rest_days(self):
        # type: () -> list
        """调休休息日（非法定节假日但放假）：按休息日口径（200%）计。"""
        calendar = (self.raw.get("params") or {}).get("holiday_calendar") or {}
        return list(calendar.get("rest_days") or [])

    def adjusted_workdays(self):
        # type: () -> list
        calendar = (self.raw.get("params") or {}).get("holiday_calendar") or {}
        return list(calendar.get("adjusted_workdays") or [])

    def holiday_day_type(self, day):
        # type: (str) -> str
        """把日期串归入日历四类之一：``statutory_holiday`` / ``rest_day`` /
        ``adjusted_workday`` / ``workday``。

        日历**唯一来源**（plan/04 §4.3）：引擎不得自行判定日期类型——否则
        政策语义会出现第二份实现。日历未覆盖的日期一律按 ``workday``。
        """
        if day in self.holiday_days():
            return "statutory_holiday"
        if day in self.rest_days():
            return "rest_day"
        if day in self.adjusted_workdays():
            return "adjusted_workday"
        return "workday"

    def __repr__(self):
        # type: () -> str
        return "Ruleset(region={!r}, year={}, status={!r})".format(
            self.region_code, self.year, self.status
        )


class Constants(object):
    """全国法定常数包。"""

    def __init__(self, raw, source_file=None):
        # type: (dict, object) -> None
        self.raw = raw
        self.source_file = source_file

    @property
    def status(self):
        # type: () -> str
        for entry in self.entries().values():
            if not entry.is_verified:
                return STATUS_PENDING
        return STATUS_VERIFIED

    def entries(self):
        # type: () -> dict
        """展平全部常数条目：``{"severance.cap_years": ParamEntry, ...}``。

        支持嵌套（``overtime.rates.workday_extension``）与列表
        （``annual_leave.entitlement_tiers[i]``）。
        """
        result = {}

        def walk(prefix, node):
            # type: (str, object) -> None
            if isinstance(node, dict):
                if "status" in node:
                    result[prefix] = ParamEntry(prefix, node)
                    return
                for key, child in node.items():
                    walk("{}.{}".format(prefix, key) if prefix else key, child)
            elif isinstance(node, list):
                for index, child in enumerate(node):
                    walk("{}[{}]".format(prefix, index), child)

        for key, node in (self.raw.get("constants") or {}).items():
            walk(key, node)
        return result

    def get(self, path):
        # type: (str) -> ParamEntry
        entries = self.entries()
        if path not in entries:
            raise ParamSchemaError("常数包缺少条目 {}".format(path))
        return entries[path]

    def __repr__(self):
        # type: () -> str
        return "Constants(status={!r}, entries={})".format(self.status, len(self.entries()))


class Regions(object):
    """地区主数据（行政区划码 + 社平工资口径登记）。"""

    def __init__(self, raw, source_file=None):
        # type: (dict, object) -> None
        self.raw = raw
        self.source_file = source_file

    @property
    def regions(self):
        # type: () -> list
        return list(self.raw.get("regions") or [])

    def codes(self):
        # type: () -> list
        return [str(item.get("code")) for item in self.regions]

    def get(self, code):
        # type: (str) -> dict
        for item in self.regions:
            if str(item.get("code")) == str(code):
                return dict(item)
        raise ParamCoordinateError("地区码 {} 不在地区主数据中".format(code))

    def __repr__(self):
        # type: () -> str
        return "Regions(count={})".format(len(self.regions))


# --------------------------------------------------------------------------
# 加载
# --------------------------------------------------------------------------

def _rules_dir(data_dir):
    # type: (str) -> str
    return os.path.join(data_dir, "rules")


def list_ruleset_files(data_dir=None):
    # type: (object) -> list
    """列出全部规则包文件（绝对路径，按文件名排序）。"""
    directory = _rules_dir(find_data_dir(data_dir))
    if not os.path.isdir(directory):
        return []
    names = sorted(name for name in os.listdir(directory) if RULES_FILENAME_RE.match(name))
    return [os.path.join(directory, name) for name in names]


def load_ruleset(region_code, year, data_dir=None, validate=True):
    # type: (str, object, object, bool) -> Ruleset
    """按精确坐标加载规则包；坐标不符或无此文件 → :class:`ParamCoordinateError`。"""
    try:
        year_int = int(year)
    except (TypeError, ValueError):
        raise ParamCoordinateError("年度非法: {!r}".format(year))

    filename = "ruleset-{}-{}.json".format(region_code, year_int)
    directory = _rules_dir(find_data_dir(data_dir))
    path = os.path.join(directory, filename)
    if not os.path.isfile(path):
        available = [
            os.path.basename(item) for item in list_ruleset_files(data_dir)
        ]
        raise ParamCoordinateError(
            "无坐标 ({}, {}) 对应的参数包（期望文件 {}）。可用规则包: {}".format(
                region_code, year_int, filename, ", ".join(available) or "（无）"
            )
        )

    ruleset = Ruleset(load_json_decimal(path), source_file=path)
    if validate:
        validate_ruleset(ruleset)
    return ruleset


def load_constants(data_dir=None, validate=True):
    # type: (object, bool) -> Constants
    path = os.path.join(find_data_dir(data_dir), "constants", "statutory-constants.json")
    if not os.path.isfile(path):
        raise ParamSchemaError("缺少法定常数包: {}".format(path))
    constants = Constants(load_json_decimal(path), source_file=path)
    if validate:
        validate_constants(constants)
    return constants


def load_regions(data_dir=None, validate=True):
    # type: (object, bool) -> Regions
    path = os.path.join(find_data_dir(data_dir), "regions", "regions.json")
    if not os.path.isfile(path):
        raise ParamSchemaError("缺少地区主数据: {}".format(path))
    regions = Regions(load_json_decimal(path), source_file=path)
    if validate:
        validate_regions(regions)
    return regions


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------

def _check_status(entry, problems):
    # type: (ParamEntry, list) -> None
    if entry.status not in _VALID_STATUS:
        problems.append("{}: status 非法 {!r}".format(entry.path, entry.status))


def _check_source(entry, required_keys, problems, label="来源"):
    # type: (ParamEntry, tuple, list, str) -> None
    """verified 条目必须挂齐来源字段（FR-1.3）。"""
    if not entry.is_verified:
        return
    source = entry.raw.get("source")
    if not isinstance(source, dict):
        problems.append("{}: status=verified 但缺少 {} 字段".format(entry.path, label))
        return
    for key in required_keys:
        if not source.get(key):
            problems.append(
                "{}: status=verified 但 {} 缺字段 {!r}".format(entry.path, label, key)
            )


def validate_ruleset(ruleset, expected_region=None, expected_year=None):
    # type: (Ruleset, object, object) -> Ruleset
    """schema 校验：坐标一致性 + 条目状态/来源。

    坐标一致性同时覆盖两个方向：
      * 文件名 ↔ 内部字段（源文件存在时）
      * 调用方期望坐标 ↔ 内部字段（expected_* 传入时）
    """
    problems = []
    raw = ruleset.raw

    if not ruleset.region_code:
        problems.append("缺少 region_code")
    if not ruleset.year:
        problems.append("缺少 year")
    if raw.get("schema_version") is None:
        problems.append("缺少 schema_version")

    params = raw.get("params")
    if not isinstance(params, dict) or not params:
        problems.append("缺少 params")
    else:
        for name in ("social_avg_wage_monthly", "min_wage_monthly", "holiday_calendar"):
            if name not in params:
                problems.append("params 缺少必需条目 {!r}".format(name))

    # 文件名 ↔ 内部坐标
    if ruleset.source_file:
        match = RULES_FILENAME_RE.match(os.path.basename(ruleset.source_file))
        if not match:
            problems.append("文件名不符合 ruleset-<region>-<year>.json: {}".format(
                os.path.basename(ruleset.source_file)))
        else:
            if match.group("region") != ruleset.region_code:
                problems.append(
                    "文件名地区码 {!r} 与内部 region_code {!r} 不一致".format(
                        match.group("region"), ruleset.region_code)
                )
            if int(match.group("year")) != ruleset.year:
                problems.append(
                    "文件名年度 {!r} 与内部 year {} 不一致".format(
                        match.group("year"), ruleset.year)
                )

    # 期望坐标 ↔ 内部坐标
    if expected_region is not None and str(expected_region) != ruleset.region_code:
        problems.append(
            "请求地区 {!r} 与参数包 region_code {!r} 不一致".format(
                expected_region, ruleset.region_code)
        )
    if expected_year is not None and int(expected_year) != ruleset.year:
        problems.append(
            "请求年度 {!r} 与参数包 year {} 不一致".format(expected_year, ruleset.year)
        )

    for entry in ruleset.entries().values():
        _check_status(entry, problems)
        if entry.path.endswith("holiday_calendar"):
            _check_source(entry, REQUIRED_SOURCE_KEYS, problems)
        else:
            _check_source(entry, REQUIRED_SOURCE_KEYS, problems)

    if problems:
        raise ParamSchemaError(
            "参数包校验失败（{}）".format(ruleset.coordinate or "未知坐标"), problems
        )
    return ruleset


def validate_constants(constants):
    # type: (Constants) -> Constants
    """常数包校验：verified 条目必须挂 ``basis``（条款 id）与 ``source.channel``。"""
    problems = []
    entries = constants.entries()
    if not entries:
        problems.append("常数包为空")
    for entry in entries.values():
        _check_status(entry, problems)
        if not entry.is_verified:
            continue
        if not entry.basis:
            problems.append("{}: status=verified 但缺 basis（条款依据）".format(entry.path))
        if not entry.source.get("channel"):
            problems.append("{}: status=verified 但缺 source.channel".format(entry.path))
    if problems:
        raise ParamSchemaError("法定常数包校验失败", problems)
    return constants


def validate_regions(regions):
    # type: (Regions) -> Regions
    problems = []
    if not regions.regions:
        problems.append("地区主数据为空")
    seen = set()
    for item in regions.regions:
        code = str(item.get("code") or "")
        if not code:
            problems.append("地区条目缺 code")
            continue
        if code in seen:
            problems.append("地区码重复: {}".format(code))
        seen.add(code)
        if not item.get("name"):
            problems.append("{}: 缺 name".format(code))
        if not item.get("avg_wage_caliber"):
            problems.append("{}: 缺 avg_wage_caliber（口径登记为必填）".format(code))
        if item.get("status") not in _VALID_STATUS:
            problems.append("{}: status 非法 {!r}".format(code, item.get("status")))
    if problems:
        raise ParamSchemaError("地区主数据校验失败", problems)
    return regions


def summarize(data_dir=None):
    # type: (object) -> dict
    """参数库概览（CLI ``params`` 子命令用）。"""
    root = find_data_dir(data_dir)
    summary = {"data_dir": root, "rulesets": [], "constants_status": None, "regions": []}
    for path in list_ruleset_files(data_dir):
        match = RULES_FILENAME_RE.match(os.path.basename(path))
        raw = load_json_decimal(path)
        summary["rulesets"].append(
            {
                "file": os.path.basename(path),
                "region_code": str(raw.get("region_code", match.group("region"))),
                "region_name": str(raw.get("region_name", "")),
                "year": int(raw.get("year", match.group("year"))),
                "status": str(raw.get("status", STATUS_PENDING)),
            }
        )
    try:
        summary["constants_status"] = load_constants(data_dir, validate=False).status
    except ParamSchemaError:
        summary["constants_status"] = None
    try:
        regions = load_regions(data_dir, validate=False)
        summary["regions"] = [
            {"code": str(item.get("code")), "name": str(item.get("name")),
             "caliber": str(item.get("avg_wage_caliber")), "status": str(item.get("status"))}
            for item in regions.regions
        ]
    except ParamSchemaError:
        summary["regions"] = []
    return summary


__all__ = [
    "RULES_FILENAME_RE",
    "STATUS_PENDING",
    "STATUS_VERIFIED",
    "REQUIRED_SOURCE_KEYS",
    "ParamEntry",
    "Ruleset",
    "Constants",
    "Regions",
    "list_ruleset_files",
    "load_ruleset",
    "load_constants",
    "load_regions",
    "validate_ruleset",
    "validate_constants",
    "validate_regions",
    "summarize",
]