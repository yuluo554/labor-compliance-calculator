"""控制台编码守卫。

背景：Windows CI 管道编码为 cp1252 时，向 stdout 打印中文会抛
``UnicodeEncodeError``；而本机中文控制台是 cp936，本身能编码中文，不该被改动。

策略：按流自身的 ``encoding`` 探针判定——**能编码中文就保持原样**，不能编码
（cp1252 / ascii / latin-1 等）才 reconfigure 为 utf-8。所有可执行入口
（CLI、tools/ 下脚本）都必须先调用本函数。
"""

from __future__ import annotations

import sys

_PROBE_TEXT = "劳动合规"


def _cannot_encode(encoding):
    # type: (object) -> bool
    if not encoding:
        return False
    try:
        _PROBE_TEXT.encode(str(encoding))
    except (UnicodeEncodeError, LookupError):
        return True
    return False


def _ensure_utf8_stdio(stream_names=("stdout", "stderr")):
    # type: (object) -> None
    """按需把指定标准流切换为 utf-8（仅在原编码无法承载中文时）。"""
    for name in stream_names:
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        if not _cannot_encode(getattr(stream, "encoding", None)):
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


__all__ = ["_ensure_utf8_stdio"]