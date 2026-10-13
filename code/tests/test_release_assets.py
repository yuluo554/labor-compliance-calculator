# -*- coding: utf-8 -*-
"""M6-4 发布附件守门：可复跑打包、台账、产物本体扫描（含阳性/阴性对照）。

三件事各有一条独立断言，且**都用阳性/阴性对照证明不是空验**：
  * ``pack`` 两次打包逐字节一致（附件哈希留档才有据链意义）；
  * ``scan`` 抓得出植入的泄露（阳性），且不误报上游构建机路径与依赖包自带 ``tests``（阴性）；
  * ``ledger`` 输出的 sha256 与磁盘文件实际哈希一致。
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
TOOL_PATH = os.path.join(REPO_ROOT, "tools", "release_assets.py")


@pytest.fixture(scope="module")
def assets():
    """以模块方式加载 tools/release_assets.py（下划线工具名不便直接 import）。"""
    spec = importlib.util.spec_from_file_location("release_assets_mod", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_dist(root):
    """合成一个最小 onedir 产物树（含二进制与子目录，覆盖排序/元数据路径）。

    ``pack`` 要求附件清单里的每个产物都在——故 cli 与 gui 都要造出来。
    """
    for stem in ("lcc-cli", "lcc-gui"):
        artifact = root / stem
        internal = artifact / "_internal"
        (internal / "data" / "rules").mkdir(parents=True)
        (artifact / (stem + ".exe")).write_bytes(b"MZ" + bytes(range(256)))
        (internal / "data" / "rules" / "110000.json").write_text('{"a": 1}\n', encoding="utf-8")
        (internal / "base_library.zip").write_bytes(b"PK\x03\x04" + b"z" * 512)
    return root


def test_selftest_passes(assets):
    """扫描器自带阳性/阴性对照：必须通过（否则它只是"什么都报 0"的空验）。"""
    assert assets.selftest() == 0


def test_pack_is_byte_reproducible(assets, tmp_path):
    """同一份 dist 两次打包 → 逐字节一致（附件 sha256 留档才有意义）。"""
    dist = _synthetic_dist(tmp_path / "dist")
    first = assets.pack(str(dist), str(tmp_path / "out1"))
    second = assets.pack(str(dist), str(tmp_path / "out2"))

    names = [os.path.basename(path) for path, _count in first]
    assert names == [os.path.basename(path) for path, _count in second]
    for (path_a, _ca), (path_b, _cb) in zip(first, second):
        digest_a = hashlib.sha256(open(path_a, "rb").read()).hexdigest()
        digest_b = hashlib.sha256(open(path_b, "rb").read()).hexdigest()
        assert digest_a == digest_b, "{} 两次打包字节不同".format(os.path.basename(path_a))


def test_pack_uses_ascii_artifact_names(assets, tmp_path):
    """附件名必须为 ASCII（跨平台解压友好、避开 gh CLI 剥中文名）。"""
    dist = _synthetic_dist(tmp_path / "dist")
    for path, _count in assets.pack(str(dist), str(tmp_path / "out")):
        name = os.path.basename(path)
        assert name.isascii(), name
        assert name.endswith(".zip")


def test_scan_detects_planted_leak(assets, tmp_path):
    """阳性对照：植入工作根标记 / 顶层禁区成分 → 必须命中。"""
    dist = _synthetic_dist(tmp_path / "dist")
    internal = dist / "lcc-cli" / "_internal"
    (internal / "leak.bin").write_bytes(b"root=" + assets.REPO_DIR_NAME.encode("utf-8"))
    (dist / "lcc-cli" / "plan").mkdir()
    (dist / "lcc-cli" / "plan" / "x.md").write_text("x", encoding="utf-8")

    hits, forbidden, _scanned = assets.scan_dist(str(dist))
    assert any(marker == "repo_dir_name" for _path, marker in hits), hits
    assert any(path.endswith("plan") for path in forbidden), forbidden


def test_scan_ignores_upstream_paths_and_dep_dirs(assets, tmp_path):
    """阴性对照：上游构建机路径与依赖包自带 tests 目录**不得**命中。"""
    dist = _synthetic_dist(tmp_path / "dist")
    internal = dist / "lcc-cli" / "_internal"
    backslash = chr(92)
    (internal / "upstream.bin").write_bytes(
        b"C:" + backslash.encode() + b"Users" + backslash.encode() + b"runneradmin" + backslash.encode() + b"work")
    (internal / "somedep" / "tests").mkdir(parents=True)
    (internal / "somedep" / "tests" / "t.py").write_text("x", encoding="utf-8")

    hits, forbidden, _scanned = assets.scan_dist(str(dist))
    assert hits == [], hits
    assert not any("somedep" in path for path in forbidden), forbidden


def test_ledger_matches_disk_hashes(assets, tmp_path):
    """台账的 sha256/字节数必须与磁盘文件一致（防手抄漂移的自动化替代）。"""
    dist = _synthetic_dist(tmp_path / "dist")
    out = tmp_path / "out"
    assets.pack(str(dist), str(out))
    entries = assets.ledger(str(out))
    assert entries, "台账为空"
    for entry in entries:
        path = out / entry["name"]
        blob = path.read_bytes()
        assert entry["bytes"] == len(blob)
        assert entry["sha256"] == hashlib.sha256(blob).hexdigest()


def test_artifact_names_match_readme(assets, repo_root):
    """README「下载即用」节引用的附件名必须与工具产出名逐字一致。"""
    readme = open(os.path.join(repo_root, "README.md"), encoding="utf-8").read()
    for _source_name, pattern in assets.ARTIFACTS:
        name = pattern.format(version="0.1.0")
        assert name in readme, "README 未引用附件名 {}".format(name)
