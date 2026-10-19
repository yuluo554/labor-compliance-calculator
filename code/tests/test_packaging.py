# -*- coding: utf-8 -*-
"""M5-5 打包守门：datas 白名单单一源、spec 复用、冻结态数据定位。

不实际调用 PyInstaller（构建耗时且需 GUI 依赖）——改为断言**结构约束**：
  * ``lcc.packaging.build_datas()`` 是白名单唯一来源（spec 不内联清单）；
  * 白名单只含显式子目录（不吞 ``data/knowledge/`` 等未入库目录）；
  * 冻结态（``sys._MEIPASS`` / exe 同级 ``_internal``）的数据定位分支可达。
"""

from __future__ import annotations

import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO_ROOT, "code", "src", "lcc")


def _read(relative):
    # type: (str) -> str
    with open(os.path.join(REPO_ROOT, relative), "r", encoding="utf-8") as handle:
        return handle.read()


def test_build_datas_covers_required_subdirs(data_dir):
    """白名单覆盖运行时必需的数据子目录，且真实存在于仓库。"""
    from lcc.packaging import REQUIRED_DATA_SUBDIRS, build_datas

    datas = build_datas(REPO_ROOT)
    destinations = {dest.replace("\\", "/") for _source, dest in datas}
    for name in REQUIRED_DATA_SUBDIRS:
        assert "data/{}".format(name) in destinations, name
    for source, _dest in datas:
        assert os.path.exists(source), source


def test_build_datas_excludes_non_whitelisted_dirs(tmp_path):
    """白名单是**显式子目录**而非目录通配：未列入的目录不得被打包。"""
    from lcc.packaging import build_datas

    data_dir = tmp_path / "data"
    for name in ("constants", "law", "regions", "rules", "truth", "knowledge"):
        (data_dir / name).mkdir(parents=True)
    (data_dir / "README.md").write_text("x", encoding="utf-8")

    datas = build_datas(str(tmp_path))
    destinations = {dest.replace("\\", "/") for _source, dest in datas}
    assert "data/knowledge" not in destinations, "未入库的快照目录不得进发布物"
    assert "data/rules" in destinations


def test_build_datas_fails_when_required_missing(tmp_path):
    """必需子目录缺失 → 打包期早失败（而非运行期找不到参数）。"""
    from lcc.packaging import build_datas

    (tmp_path / "data" / "constants").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        build_datas(str(tmp_path))


def test_specs_share_single_datas_source():
    """两个 spec 都调用 ``build_datas``，均不内联文件清单（D-19 单一源）。"""
    for relative in ("tools/lcc-cli.spec", "tools/lcc-gui.spec"):
        text = _read(relative)
        assert "build_datas" in text, "{} 应调用 lcc.packaging.build_datas".format(relative)
        assert "lcc.packaging" in text
        # 不得出现手写的数据目录字面量清单
        assert "data/rules" not in text, "{} 不得内联数据文件清单".format(relative)


def test_specs_exclude_pil_and_lxml():
    """两个 spec 必须排除 PIL / lxml（openpyxl 的可选图像/XML 依赖，约 17 MB）。

    XLSX 写出路径只用 stdlib；排除后仍需实测导出成功（见 verify_package）。
    """
    for relative in ("tools/lcc-cli.spec", "tools/lcc-gui.spec"):
        text = _read(relative)
        match = re.search(r"excludes=\[([^\]]*)\]", text)
        assert match, "{} 缺少 excludes 列表".format(relative)
        excluded = {
            item.strip().strip('"').strip("'")
            for item in match.group(1).split(",")
            if item.strip()
        }
        assert "PIL" in excluded, "{} 未排除 PIL".format(relative)
        assert "lxml" in excluded, "{} 未排除 lxml".format(relative)


def test_specs_are_tracked_despite_gitignore():
    """``.gitignore`` 的 ``*.spec`` 必须放行 ``tools/*.spec``（否则发布物入不了仓）。"""
    text = _read(".gitignore")
    assert "*.spec" in text
    assert "!tools/*.spec" in text


def test_entry_scripts_exist_and_add_src_path():
    """打包入口脚本存在，并把 ``code/src`` 加入 sys.path（源码态可跑）。"""
    for relative in ("tools/entry_cli.py", "tools/entry_gui.py"):
        path = os.path.join(REPO_ROOT, relative)
        assert os.path.isfile(path), relative
        text = _read(relative)
        assert "code" in text and "src" in text
        assert "lcc" in text


def test_frozen_data_dir_lookup_branches(monkeypatch, tmp_path, data_dir):
    """冻结态数据定位：``sys._MEIPASS/data`` 与 exe 同级 ``_internal/data`` 均可达。"""
    from lcc import data_paths

    monkeypatch.delenv(data_paths.ENV_VAR, raising=False)

    # 6.x：sys._MEIPASS/data
    meipass_root = tmp_path / "six-bundle"
    (meipass_root / "data" / "rules").mkdir(parents=True)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_root), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "elsewhere" / "lcc-gui.exe"))
    assert data_paths.find_data_dir() == os.path.abspath(str(meipass_root / "data"))

    # 5.x 兼容：exe 同级 _internal/data（无 _MEIPASS）
    exe_root = tmp_path / "five-bundle"
    (exe_root / "_internal" / "data" / "rules").mkdir(parents=True)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_root / "lcc-gui.exe"))
    assert data_paths.find_data_dir() == os.path.abspath(
        str(exe_root / "_internal" / "data"))


def test_frozen_flag_detects_pyinstaller(monkeypatch):
    from lcc import data_paths

    monkeypatch.delattr(sys, "frozen", raising=False)
    assert data_paths.is_frozen() is False
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert data_paths.is_frozen() is True
