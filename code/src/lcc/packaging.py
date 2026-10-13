"""打包（PyInstaller）辅助——**datas 白名单的唯一来源**（D-19）。

为什么放在包内而不是 ``tools/``：
  * 顶层模块名 ``packaging`` 会**遮蔽 PyPI 的 ``packaging``**（PyInstaller 自身
    依赖它做版本判断），放在 ``tools/`` 并在 spec 里加 ``sys.path`` 会打挂构建；
  * 数据布局与 :mod:`lcc.data_paths` 的冻结态查找规则是同一件事的两面
    （一个决定"装到哪"，一个决定"从哪找"），放同一包内便于对齐。

spec 文件（``tools/lcc-gui.spec`` / ``tools/lcc-cli.spec``）只调用
:func:`build_datas`，不各自维护文件清单——避免"两个 spec 各写一份白名单"漂移。

本模块是**纯 stdlib**（仅 ``os``），可被核心层守门测试接受。
"""

from __future__ import annotations

import os

# 运行时必需的数据子目录（白名单；顺序即打包顺序，稳定可复现）
REQUIRED_DATA_SUBDIRS = (
    "constants",
    "law",
    "regions",
    "rules",
)

# 随包附带但非运行时必需（供用户核对口径/复核算例）
OPTIONAL_DATA_SUBDIRS = (
    "truth",
)

# 源仓库根（本文件在 code/src/lcc/ 下）
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)
DATA_DIR = os.path.join(REPO_ROOT, "data")


def build_datas(repo_root=None, include_optional=True):
    # type: (object, bool) -> list
    """产出 PyInstaller 的 ``datas`` 列表：``[(源路径, 包内相对路径), ...]``。

    白名单**只含数据目录下的显式子目录**（不做目录通配），确保 ``data/knowledge/``
    等未入库快照目录不会被卷进发布物。缺失的必需子目录 → :class:`FileNotFoundError`
    （打包期早失败，而非运行期找不到参数）。
    """
    root = os.path.abspath(repo_root or REPO_ROOT)
    data_dir = os.path.join(root, "data")
    if not os.path.isdir(data_dir):
        raise FileNotFoundError("数据目录不存在: {}".format(data_dir))

    names = list(REQUIRED_DATA_SUBDIRS)
    if include_optional:
        names.extend(OPTIONAL_DATA_SUBDIRS)

    datas = []
    for name in names:
        source = os.path.join(data_dir, name)
        if not os.path.isdir(source):
            if name in REQUIRED_DATA_SUBDIRS:
                raise FileNotFoundError("必需数据子目录缺失: {}".format(source))
            continue
        datas.append((source, os.path.join("data", name)))

    top_level = os.path.join(data_dir, "README.md")
    if os.path.isfile(top_level):
        datas.append((top_level, "data"))
    return datas


def data_dir_for_runtime():
    # type: () -> str
    """仓库态下的数据目录（供打包脚本提示用，不参与冻结态查找）。"""
    return DATA_DIR


def build_datas_manifest(repo_root=None, include_optional=True):
    # type: (object, bool) -> list
    """白名单的**可读清单**（相对仓库根，供文档与验证脚本对账）。"""
    root = os.path.abspath(repo_root or REPO_ROOT)
    entries = []
    for source, destination in build_datas(root, include_optional):
        rel_source = os.path.relpath(source, root).replace("\\", "/")
        rel_dest = destination.replace("\\", "/")
        entries.append({"source": rel_source, "dest": rel_dest})
    return entries


__all__ = [
    "REQUIRED_DATA_SUBDIRS",
    "OPTIONAL_DATA_SUBDIRS",
    "REPO_ROOT",
    "DATA_DIR",
    "build_datas",
    "build_datas_manifest",
    "data_dir_for_runtime",
]
