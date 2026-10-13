"""Decimal 口径与 JSON 加载（plan/04；NFR-3）。

纪律：
  * 所有金额/天数在引擎内一律 ``Decimal``；JSON 加载用 ``parse_float=Decimal``，
    绝不让 float 进入计算路径（1 分差异必须可检出）。
  * 呈现量化口径统一两位小数 ``ROUND_HALF_UP``——这是**精度约定**（非政策数值），
    故豁免零政策字面量门禁（见 tools/check_no_literals.py 的豁免口径）。
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANTUM = Decimal("0.01")
_ONE = Decimal(1)
_ZERO = Decimal(0)


def to_decimal(value, field="value"):
    # type: (object, str) -> Decimal
    """把 str/int/Decimal/float 转 Decimal；bool 与非法类型报错。

    float 走 ``str(value)`` 而非 ``Decimal(value)``——避免二进制尾差被固化
    （例：``Decimal(0.1)`` 是 0.1000000000000000055511151231257827）。
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("{}: 布尔值不是合法数值".format(field))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("{}: 空字符串不是合法数值".format(field))
        return Decimal(text)
    raise TypeError("{}: 不支持的数值类型 {}".format(field, type(value).__name__))


def quantize_money(value):
    # type: (Decimal) -> Decimal
    """金额呈现口径：两位小数，ROUND_HALF_UP。"""
    return to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def load_json_decimal(path):
    # type: (str) -> object
    """读 JSON，浮点字面量一律解析为 Decimal。"""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def money_str(value):
    # type: (Decimal) -> str
    """金额序列化：固定两位小数字符串（写回 JSON / 报告用）。"""
    return str(quantize_money(value))


def decimal_default(obj):
    # type: (object) -> object
    """json.dumps(default=...) 用：Decimal → 字符串（保精度）。"""
    if isinstance(obj, Decimal):
        return money_str(obj)
    raise TypeError("不可序列化类型: {}".format(type(obj).__name__))


__all__ = [
    "MONEY_QUANTUM",
    "to_decimal",
    "quantize_money",
    "load_json_decimal",
    "money_str",
    "decimal_default",
]