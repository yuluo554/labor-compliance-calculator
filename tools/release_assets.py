#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""发布附件工具（M6-4）：可复跑打包 + 台账 + 产物本体扫描。

三个子命令对应「发布四步」里的两步（产物本体扫描）与「附件可复跑」纪律：

``scan``    构建产物**本体**扫描：全 dist 树按**字节读法**匹配强标记（我们的工作根
            组合签名 / 本机用户目录 / 盘符路径），并复核产物树**顶层**无禁区成分
            （``plan`` / ``tests`` / ``code`` / ``_private`` / ``.git`` / ``__pycache__`` /
            ``*.egg-info`` / ``*.pyc``）。内容级扫描只能证明"仓库树干净"，证明不了
            "冻结产物干净"——exe 会内嵌构建机源码路径，这是独立的一步。
``pack``    把 onedir 产物打成**可复跑** zip：ASCII 文件名（跨平台解压友好、避开
            gh CLI 剥中文名）、固定 ``date_time`` 与 ``create_system``、条目按名排序
            → 同一份 dist 两次打包**逐字节一致**。注意区分：可复跑的是**打包这一步**；
            PyInstaller 产物本身非字节确定（重建 dist → 新 zip 哈希），留档写清哪一步。
``ledger``  输出 JSON 台账（附件名 / sha256 / 字节数），供 ``plan/RELEASE-M6.md``
            直接引用，避免手抄漂移。

为什么强标记要绑"我们的工作根"：PyInstaller 与 Qt 的上游二进制自带**构建机**路径
（如 ``C:\\Users\\runneradmin\\...``），按裸 ``C:\\Users\\`` 匹配会成片误报。只匹配
**本项目工作根的组合签名**（仓库目录名 + 其父目录片段）才是真实泄露面。

用法：
    py -X utf8 tools/release_assets.py scan
    py -X utf8 tools/release_assets.py pack --out _backups/release
    py -X utf8 tools/release_assets.py ledger --out _backups/release
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "code", "src"))

try:
    from lcc._stdio import _ensure_utf8_stdio
except ImportError:  # 兜底：脱离仓库布局时仍可运行
    def _ensure_utf8_stdio(stream_names=("stdout", "stderr")):
        # type: (object) -> None
        for name in stream_names:
            stream = getattr(sys, name, None)
            if stream is None:
                continue
            encoding = getattr(stream, "encoding", None) or ""
            try:
                "劳动合规".encode(encoding)
            except (UnicodeEncodeError, LookupError):
                reconfigure = getattr(stream, "reconfigure", None)
                if reconfigure is not None:
                    try:
                        reconfigure(encoding="utf-8")
                    except (ValueError, OSError):
                        pass

# ---- 发布附件清单（ASCII 名；与 README「下载即用」节逐字一致）----------------
ARTIFACTS = (
    ("lcc-cli", "lcc-cli-{version}-win64.zip"),
    ("lcc-gui", "lcc-gui-{version}-win64.zip"),
)

# 打包固定时间戳（zip 最小可表示时刻；不用当前时间 → 打包可复跑）
FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)

# ---- 产物本体扫描的强标记（片段拼接构造，防扫描器自命中）---------------------
# 组合签名：只匹配**本项目工作根**，不匹配裸的"用户目录盘符路径"（上游二进制
# 自带构建机路径，按裸路径匹配会成片误报）。
# 注意这里是**字节子串**匹配（不是正则）：反斜杠写一个即可——写成两个字符与真实
# 路径不符（本工具 selftest 的阳性对照实测抓出过这个 bug）。
REPO_DIR_NAME = "10-13-labor-compliance-calculator"
_WORK_ROOT_PARENT = "ProgramData" + "\\" + "zcode"
_LOCAL_USER_DIR = "Users" + "\\" + "ASUS"

STRONG_MARKERS = (
    ("repo_dir_name", REPO_DIR_NAME.encode("utf-8")),
    ("work_root_parent", _WORK_ROOT_PARENT.encode("utf-8")),
    ("work_root_parent_posix", _WORK_ROOT_PARENT.replace("\\", "/").encode("utf-8")),
    ("local_user_dir", _LOCAL_USER_DIR.encode("utf-8")),
    ("local_user_dir_posix", _LOCAL_USER_DIR.replace("\\", "/").encode("utf-8")),
)

# 产物树**顶层**禁区成分（任意层级匹配会把依赖包自带的同名目录当命中，故只查顶层）
FORBIDDEN_TOP_LEVEL = re.compile(r"^(plan|tests|code|_private|\.git|__pycache__)$")
FORBIDDEN_TOP_SUFFIXES = (".egg-info", ".pyc")


def _version():
    # type: () -> str
    sys.path.insert(0, os.path.join(ROOT, "code", "src"))
    try:
        from lcc import __version__
        return __version__
    except ImportError:
        return "0.0.0"


def _iter_files(root):
    # type: (str) -> list
    """稳定顺序遍历（排序保证打包可复跑）。"""
    collected = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            collected.append(os.path.join(dirpath, name))
    return collected


def _sha256(path):
    # type: (str) -> str
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---- scan ------------------------------------------------------------------

def _top_level_names(dist_dir):
    # type: (str) -> list
    """产物树的"顶层"清单：每个 onedir 根目录 + 其 ``_internal`` 子目录。

    为什么不是"dist 的顶层"：PyInstaller onedir 把内容放进 ``dist/<name>/``，
    真正的"我们的东西混进来了"表现为 ``dist/<name>/plan`` 或
    ``dist/<name>/_internal/plan``。按任意层级匹配则会把**依赖包自带**的同名
    子目录（如某库的 ``tests/``）当命中——故只看这两层。
    """
    names = []
    for entry in sorted(os.listdir(dist_dir)):
        artifact_root = os.path.join(dist_dir, entry)
        if not os.path.isdir(artifact_root):
            continue
        names.append((entry, entry))
        for sub in sorted(os.listdir(artifact_root)):
            names.append((entry, "{}/{}".format(entry, sub)))
        internal = os.path.join(artifact_root, "_internal")
        if os.path.isdir(internal):
            for sub in sorted(os.listdir(internal)):
                names.append((entry, "{}/_internal/{}".format(entry, sub)))
    return names


def scan_dist(dist_dir):
    # type: (str) -> tuple
    """产物本体扫描。返回 ``(hits, forbidden, scanned)``。

    ``hits`` = ``[(相对路径, 标记名)]``；``forbidden`` = ``[相对路径]``。
    输出只报**文件路径与类别**，不回显敏感原文（报告可随仓留档）。
    """
    hits, forbidden = [], []
    scanned = 0

    for _artifact, relative in _top_level_names(dist_dir):
        base = os.path.basename(relative)
        if FORBIDDEN_TOP_LEVEL.match(base) or base.endswith(FORBIDDEN_TOP_SUFFIXES):
            forbidden.append(relative)

    for dirpath, dirnames, filenames in os.walk(dist_dir):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            relative = os.path.relpath(path, dist_dir).replace("\\", "/")
            try:
                with open(path, "rb") as handle:
                    blob = handle.read()
            except OSError:
                continue
            scanned += 1
            for marker_name, marker in STRONG_MARKERS:
                if marker in blob:
                    hits.append((relative, marker_name))
    return hits, forbidden, scanned


# ---- pack ------------------------------------------------------------------

def pack(dist_dir, out_dir, version=None):
    # type: (str, str, object) -> list
    """把每个 onedir 产物打成确定性 zip。返回 ``[(zip 路径, 条目数)]``。"""
    version = version or _version()
    os.makedirs(out_dir, exist_ok=True)
    produced = []
    for source_name, pattern in ARTIFACTS:
        source = os.path.join(dist_dir, source_name)
        if not os.path.isdir(source):
            raise FileNotFoundError("未找到打包产物: {}".format(source))
        target = os.path.join(out_dir, pattern.format(version=version))
        files = _iter_files(source)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                relative = os.path.relpath(path, source).replace("\\", "/")
                info = zipfile.ZipInfo("{}/{}".format(source_name, relative),
                                       date_time=FIXED_ZIP_DATETIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0          # 固定容器元数据（跨平台不漂移）
                info.external_attr = 0o644 << 16
                with open(path, "rb") as handle:
                    archive.writestr(info, handle.read())
        produced.append((target, len(files)))
    return produced


def ledger(out_dir, version=None):
    # type: (str, object) -> list
    """读回 out_dir 里的附件，产出台账条目（名 / sha256 / 字节数）。"""
    version = version or _version()
    entries = []
    for _source_name, pattern in ARTIFACTS:
        path = os.path.join(out_dir, pattern.format(version=version))
        if not os.path.isfile(path):
            raise FileNotFoundError("未找到附件: {}（先跑 pack）".format(path))
        entries.append({
            "name": os.path.basename(path),
            "sha256": _sha256(path),
            "bytes": os.path.getsize(path),
        })
    return entries


def selftest():
    # type: () -> int
    """阳性/阴性对照：证明扫描器**不是**"什么都报 0"的空验。

    阳性对照：在临时目录合成带强标记与顶层禁区成分的假产物 → 必须全部命中。
    阴性对照：上游二进制常见的**构建机路径**（别人的 ``C:\\Users\\<他人>``）与
    依赖包自带的 ``tests`` 子目录 → 必须**不**命中（防成片误报）。
    夹具全部程序化合成，源码内无真实敏感字面值。
    """
    import tempfile

    backslash = chr(92)
    failures = []

    with tempfile.TemporaryDirectory(prefix="lcc-scan-selftest-") as root:
        internal = os.path.join(root, "lcc-cli", "_internal")
        os.makedirs(internal)
        # 阳性对照
        with open(os.path.join(internal, "leak_repo.bin"), "wb") as handle:
            handle.write(b"path=" + REPO_DIR_NAME.encode("utf-8") + b"/code")
        with open(os.path.join(internal, "leak_user.bin"), "wb") as handle:
            handle.write(b"C:" + backslash.encode() + _LOCAL_USER_DIR.encode("utf-8") + b"/x")
        with open(os.path.join(internal, "leak_root.bin"), "wb") as handle:
            handle.write(_WORK_ROOT_PARENT.encode("utf-8") + b"/repo")
        os.makedirs(os.path.join(root, "lcc-cli", "plan"))
        with open(os.path.join(root, "lcc-cli", "plan", "x.md"), "w", encoding="utf-8") as handle:
            handle.write("x")
        # 阴性对照：上游构建机路径 + 依赖包自带 tests 目录
        with open(os.path.join(internal, "upstream.bin"), "wb") as handle:
            handle.write(b"C:" + backslash.encode() + b"Users" + backslash.encode()
                         + b"runneradmin" + backslash.encode() + b"work")
        os.makedirs(os.path.join(internal, "somedep", "tests"))
        with open(os.path.join(internal, "somedep", "tests", "t.py"), "w", encoding="utf-8") as handle:
            handle.write("x")

        hits, forbidden, scanned = scan_dist(root)
        hit_names = {marker for _path, marker in hits}
        expected = {"repo_dir_name", "local_user_dir", "work_root_parent"}
        missing = expected - hit_names
        if missing:
            failures.append("阳性对照漏报: {}".format(sorted(missing)))
        if not any(path.endswith("plan") for path in forbidden):
            failures.append("顶层禁区成分漏报（plan）")
        if any("somedep/tests" in path for path in forbidden):
            failures.append("阴性对照误报：依赖包自带 tests 被当顶层禁区")
        if any("upstream.bin" in path for _p, _m in hits for path in [_p]):
            failures.append("阴性对照误报：上游构建机路径被当本机泄露")
        if scanned < 6:
            failures.append("扫描面过小（{} 文件），疑未遍历到对照夹具".format(scanned))

    if failures:
        for message in failures:
            sys.stderr.write("  {}\n".format(message))
        sys.stderr.write("RELEASE_ASSETS_SELFTEST_FAIL\n")
        return 1
    sys.stdout.write("RELEASE_ASSETS_SELFTEST_OK\n")
    return 0


def main(argv=None):
    # type: (object) -> int
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="发布附件工具（可复跑打包 / 台账 / 产物扫描）")
    parser.add_argument("command", choices=("scan", "pack", "ledger", "selftest"))
    parser.add_argument("--dist", default=os.path.join(ROOT, "dist"), help="dist 目录")
    parser.add_argument("--out", default=os.path.join(ROOT, "_backups", "release"),
                        help="附件输出目录（pack/ledger）")
    parser.add_argument("--json", action="store_true", help="输出 JSON（ledger 恒为 JSON）")
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return selftest()

    dist_dir = os.path.abspath(args.dist)
    out_dir = os.path.abspath(args.out)

    if args.command == "scan":
        if not os.path.isdir(dist_dir):
            sys.stderr.write("未找到 dist 目录: {}（先跑 tools/build_release.py）\n".format(dist_dir))
            return 2
        hits, forbidden, scanned = scan_dist(dist_dir)
        sys.stdout.write("扫描文件数: {}\n".format(scanned))
        if hits:
            sys.stdout.write("强标记命中（{} 处）:\n".format(len(hits)))
            for relative, marker in hits:
                sys.stdout.write("  {} [{}]\n".format(relative, marker))
        if forbidden:
            sys.stdout.write("顶层禁区成分（{} 处）:\n".format(len(forbidden)))
            for relative in forbidden:
                sys.stdout.write("  {}\n".format(relative))
        if hits or forbidden:
            sys.stderr.write("\n产物本体扫描失败：命中须清除或占位化后重打包。\n")
            return 1
        sys.stdout.write("DIST_SCAN_OK\n")
        return 0

    if args.command == "pack":
        if not os.path.isdir(dist_dir):
            sys.stderr.write("未找到 dist 目录: {}（先跑 tools/build_release.py）\n".format(dist_dir))
            return 2
        produced = pack(dist_dir, out_dir)
        for path, count in produced:
            sys.stdout.write("[OK] {}（{} 条目）\n".format(path, count))
        sys.stdout.write("RELEASE_PACK_OK\n")
        return 0

    entries = ledger(out_dir)
    sys.stdout.write(json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
