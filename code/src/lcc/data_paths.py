"""数据目录定位（仓库态 / 冻结态统一入口）。

解析优先级（plan/03；分支行为锁进 tests/test_data_paths.py）：
  1. 显式传入的路径
  2. 环境变量 ``LCC_DATA_DIR``
  3. PyInstaller 冻结态：``sys._MEIPASS/data``（6.x）→ ``exe目录/_internal/data``（5.x 兼容）
  4. 源码态：从本文件向上回溯，命中含 ``data/`` 的项目根
  5. 当前工作目录向上回溯
"""

from __future__ import annotations

import os
import sys

ENV_VAR = "LCC_DATA_DIR"
_MARKER = "rules"


def _is_data_dir(path):
    # type: (str) -> bool
    return bool(path) and os.path.isdir(os.path.join(path, _MARKER))


def _frozen_candidates():
    # type: () -> list
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "data"))
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates.append(os.path.join(exe_dir, "data"))
    candidates.append(os.path.join(exe_dir, "_internal", "data"))
    return candidates


def _walk_up_candidates(start):
    # type: (str) -> list
    candidates = []
    current = os.path.abspath(start)
    while True:
        candidates.append(os.path.join(current, "data"))
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return candidates


def find_data_dir(explicit=None):
    # type: (object) -> str
    """定位数据目录；找不到抛 FileNotFoundError（含已尝试路径）。

    显式传入的路径**不参与回退**——给错即报错，避免"以为指定了 A 实际用了 B"
    的假绿（验证场景尤其危险）。
    """
    tried = []
    if explicit:
        tried.append(str(explicit))
        if _is_data_dir(str(explicit)):
            return os.path.abspath(str(explicit))
        raise FileNotFoundError(
            "指定的数据目录不可用: {}（需含 {!r} 子目录）".format(explicit, _MARKER)
        )

    env_value = os.environ.get(ENV_VAR)
    if env_value:
        tried.append(env_value)
        if _is_data_dir(env_value):
            return os.path.abspath(env_value)
        raise FileNotFoundError(
            "环境变量 {} 指向的数据目录不可用: {}".format(ENV_VAR, env_value)
        )

    tried.extend(_frozen_candidates())
    for candidate in _frozen_candidates():
        if _is_data_dir(candidate):
            return os.path.abspath(candidate)

    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in _walk_up_candidates(here) + _walk_up_candidates(os.getcwd()):
        tried.append(candidate)
        if _is_data_dir(candidate):
            return os.path.abspath(candidate)

    raise FileNotFoundError(
        "未找到数据目录（需含 {!r} 子目录）。已尝试：\n  {}".format(_MARKER, "\n  ".join(tried))
    )


def is_frozen():
    # type: () -> bool
    return bool(getattr(sys, "frozen", False))


__all__ = ["ENV_VAR", "find_data_dir", "is_frozen"]