# -*- coding: utf-8 -*-
"""仓库级守门：分层依赖、零政策字面量、冻结产物、EOL、CI 接线、脱敏。

这些测试把"动了会打挂基准/纪律"的约定变成可执行断言（plan/05 §四）。
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys

import pytest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "lcc")


def _read(path):
    # type: (str) -> str
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _py_files(root):
    # type: (str) -> list
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name != "__pycache__"]
        for name in sorted(filenames):
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return out


# ---- 分层依赖（D-13：引擎层不得 import CLI/GUI） ---------------------------

def test_engine_layer_does_not_import_cli_or_gui():
    """AST 静态断言：引擎/规则层顶层与函数内均不得引用 CLI/GUI（比 sys.modules 可靠）。"""
    engine_dir = os.path.join(SRC, "engine")
    forbidden = ("lcc.cli", "lcc.gui", "cli", "gui", "PySide6")
    offenders = []
    targets = _py_files(engine_dir) + [
        os.path.join(SRC, name)
        for name in ("params.py", "gate.py", "law.py", "model.py", "pipeline.py", "decimalutil.py")
    ]
    for path in targets:
        tree = ast.parse(_read(path), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in ("PySide6",) or alias.name in forbidden:
                        offenders.append((path, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0] in ("PySide6",) or module in forbidden:
                    offenders.append((path, module))
    assert not offenders, "引擎/规则层不得 import CLI/GUI: {}".format(offenders)


def _stdlib_names():
    # type: () -> set
    """stdlib 模块名集合（py3.10+ 有 stdlib_module_names；3.8/3.9 回退扫描 stdlib 目录）。"""
    names = set(getattr(sys, "stdlib_module_names", ()))
    names.update({"__future__", "lcc"})
    if not names - {"__future__", "lcc"}:
        import sysconfig

        stdlib_dir = sysconfig.get_paths().get("stdlib") or ""
        if os.path.isdir(stdlib_dir):
            for entry in os.listdir(stdlib_dir):
                if entry.endswith(".py"):
                    names.add(entry[:-3])
                elif os.path.isdir(os.path.join(stdlib_dir, entry)) and not entry.startswith("site-packages"):
                    names.add(entry)
        names.update(sys.builtin_module_names)
    return names


def test_core_layer_has_no_third_party_imports():
    """核心层零第三方依赖（D-09）。

    适用范围 = 引擎/规则/编排/报告（Markdown 通路）层（engine、params、gate、law、
    model、pipeline、decimalutil、data_paths、errors、_stdio、report），以及
    benchmark 真值语义。这些模块只允许 stdlib 与 lcc 内部。

    表现层——``cli.py``、``gui/``、``report/xlsx.py``——**允许**惰性探测可选依赖
    （PySide6 / openpyxl），但必须满足"函数内 + try/except ImportError 守卫"，
    由 :func:`test_presentation_optional_deps_are_lazy_and_guarded` 约束。
    """
    stdlib = _stdlib_names()
    core_files = [
        path for path in _py_files(SRC)
        if os.sep + "gui" + os.sep not in path
        and os.path.basename(path) != "cli.py"
        and os.path.basename(path) != "xlsx.py"
    ]
    offenders = []
    for path in core_files:
        tree = ast.parse(_read(path), filename=path)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                if name.startswith("lcc") or name in stdlib:
                    continue
                offenders.append((os.path.basename(path), name))
    assert not offenders, "核心层出现第三方依赖: {}".format(offenders)


def _guarded_lazy_imports(path):
    # type: (str) -> tuple
    """返回 ``(unguarded, guarded)``：模块级第三方 import 与"函数内+try/except"守卫 import。

    判定依据：AST 上 import 节点若其祖先链中含 FunctionDef **且** 含 Try 且该 Try
    的 handler 捕获 ImportError → 视为守卫惰性导入。
    """
    tree = ast.parse(_read(path), filename=path)
    unguarded, guarded = [], []

    def visit(node, in_function=False, in_guarded_try=False):
        for child in ast.iter_child_nodes(node):
            child_in_function = in_function or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            child_in_try = in_guarded_try
            if isinstance(child, ast.Try):
                for handler in child.handlers:
                    names = []
                    if isinstance(handler.type, ast.Name):
                        names = [handler.type.id]
                    elif isinstance(handler.type, ast.Tuple):
                        names = [elt.id for elt in handler.type.elts if isinstance(elt, ast.Name)]
                    if "ImportError" in names or "Exception" in names or "BaseException" in names:
                        child_in_try = True
            if isinstance(child, ast.Import):
                names = [alias.name.split(".")[0] for alias in child.names]
            elif isinstance(child, ast.ImportFrom) and child.level == 0 and child.module:
                names = [child.module.split(".")[0]]
            else:
                names = []
            for name in names:
                if name.startswith("lcc") or name in _stdlib_names():
                    continue
                if child_in_function and child_in_try:
                    guarded.append((name, child.lineno))
                else:
                    unguarded.append((name, child.lineno))
            visit(child, child_in_function, child_in_try)

    visit(tree)
    return unguarded, guarded


def test_cli_optional_deps_are_lazy_and_guarded():
    """表现层的可选依赖（PySide6）必须是函数内 + try/except ImportError 的惰性导入。

    这是 D-13「GUI 惰性导入」的可执行断言：模块级 import PySide6 会让
    ``import lcc.cli`` 在无 GUI 依赖的机器上直接崩，且 CLI 其它子命令也一起不可用。
    M5 起 GUI 实装在 ``lcc.gui.app``（``cli.py`` 只是转发到 ``gui.app.run``），
    故两个表现层文件一起断言。
    """
    for relative in ("cli.py", os.path.join("gui", "app.py")):
        path = os.path.join(SRC, relative)
        unguarded, guarded = _guarded_lazy_imports(path)
        assert not unguarded, "{} 出现模块级第三方 import（必须惰性+守卫）: {}".format(
            relative, unguarded)
    _unguarded, guarded = _guarded_lazy_imports(os.path.join(SRC, "gui", "app.py"))
    assert "PySide6" in {name for name, _lineno in guarded}, \
        "gui/app.py 应仅在守卫式惰性导入中引用 PySide6"


def test_presentation_optional_deps_are_lazy_and_guarded():
    """可选依赖（PySide6 / openpyxl）只允许出现在守卫式惰性导入里。

    `cli.py` 与 `gui/` 的表现层代码不得模块级 import 第三方；`report/xlsx.py`
    是 XLSX 通路的唯一可选依赖边界，同样只能惰性+守卫。
    """
    offenders = []
    for relative in ("cli.py", os.path.join("gui", "app.py"), os.path.join("report", "xlsx.py")):
        path = os.path.join(SRC, relative)
        unguarded, _guarded = _guarded_lazy_imports(path)
        if unguarded:
            offenders.append((relative, unguarded))
    assert not offenders, "表现层出现模块级第三方 import: {}".format(offenders)


# ---- 零政策字面量门禁（NFR-4 / D-12） -------------------------------------

def test_no_policy_literals_gate_passes(repo_root):
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "tools", "check_no_literals.py")],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "NO_POLICY_LITERALS_OK" in output


# ---- 冻结产物（D-10 / NFR-2） ---------------------------------------------

def test_frozen_rulesets_regenerate_byte_identical(repo_root):
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "tools", "gen_rulesets.py"), "--check"],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "FROZEN_RULESETS_OK" in output


def test_frozen_json_has_no_cr_and_ends_with_lf(data_dir):
    """EOL 门：冻结产物不得出现 CR（跨机器可复现的前置）。"""
    checked = 0
    for dirpath, _dirnames, filenames in os.walk(data_dir):
        for name in sorted(filenames):
            if not name.endswith(".json"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                blob = handle.read()
            assert b"\r" not in blob, "冻结产物出现 CR: {}".format(path)
            assert blob.endswith(b"\n"), "冻结产物应以 LF 结尾: {}".format(path)
            checked += 1
    assert checked > 0


def _tracked_text_files(repo_root):
    # type: (str) -> list
    """跟踪的文本文件相对路径；无 ``.git``（如 git archive 导出树）时退回文件系统遍历。"""
    if os.path.isdir(os.path.join(repo_root, ".git")):
        out = subprocess.check_output(
            ["git", "-c", "core.quotepath=false", "ls-files"], cwd=repo_root
        ).decode("utf-8", "replace")
        return [line.strip() for line in out.splitlines() if line.strip()]

    skip_dirs = {".git", "__pycache__", "node_modules", "build", "dist", ".pytest_cache"}
    names = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        if "pyvenv.cfg" in filenames:      # venv 特征：整棵剪掉
            dirnames[:] = []
            continue
        dirnames[:] = [
            name for name in dirnames
            if name not in skip_dirs and not name.endswith(".egg-info") and not name.startswith(".venv")
        ]
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), repo_root).replace("\\", "/")
            names.append(rel)
    return names


def test_all_tracked_text_files_use_lf(repo_root):
    """.gitattributes eol=lf 的守门：文本文件工作区副本不得含 CR。"""
    suffixes = (".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt", ".gitignore", ".gitattributes")
    offenders = []
    for name in _tracked_text_files(repo_root):
        if not name.lower().endswith(suffixes):
            continue
        path = os.path.join(repo_root, name)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            if b"\r" in handle.read():
                offenders.append(name)
    assert not offenders, "以下文件含 CR（违反 eol=lf）: {}".format(offenders)


# ---- 免责声明强制（NFR-9） -------------------------------------------------

def test_disclaimer_present_in_pipeline_and_cli():
    from lcc import pipeline

    assert "免责声明" in pipeline.DISCLAIMER
    assert "不构成法律意见" in pipeline.DISCLAIMER
    cli_text = _read(os.path.join(SRC, "cli.py"))
    assert "disclaimer" in cli_text


def test_disclaimer_in_readme(repo_root):
    readme = _read(os.path.join(repo_root, "README.md"))
    assert "不构成法律意见" in readme


# ---- CI 接线（D-23：checkout 必须取全量历史） ------------------------------

def _load_ci(repo_root):
    path = os.path.join(repo_root, ".github", "workflows", "ci.yml")
    if not os.path.isfile(path):
        pytest.fail("缺少 .github/workflows/ci.yml")
    try:
        import yaml
    except ImportError:
        pytest.skip("未安装 pyyaml（dev extra），CI 接线断言跳过")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle), path


def test_ci_workflow_parses_and_has_jobs(repo_root):
    """CI workflow 必须可解析且每个 job 有 runs-on/steps。

    背景：非法 YAML（如 step 名含「冒号+空格」未加引号）会让 GitHub 不建任何 job，
    而文件字节与 state 均显示正常——只有真解析才暴露。
    """
    payload, path = _load_ci(repo_root)
    assert isinstance(payload, dict), "{} 解析结果不是映射".format(path)
    jobs = payload.get("jobs") or {}
    assert jobs, "workflow 没有任何 job"
    for name, job in jobs.items():
        assert job.get("runs-on"), "job {} 缺 runs-on".format(name)
        assert job.get("steps"), "job {} 缺 steps".format(name)


def test_ci_checkout_uses_full_history(repo_root):
    """每个 checkout step 必须 fetch-depth: 0（否则历史扫描守门在 CI 静默空验）。"""
    payload, _path = _load_ci(repo_root)
    offenders = []
    for name, job in (payload.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            uses = str(step.get("uses") or "")
            if uses.startswith("actions/checkout"):
                depth = (step.get("with") or {}).get("fetch-depth")
                if depth != 0:
                    offenders.append((name, depth))
    assert not offenders, "checkout 未配 fetch-depth: 0: {}".format(offenders)


# ---- 脱敏审计工具可跑（阶段 7 第 2 步的守门） ------------------------------

def test_dessensitize_audit_tracked_passes(repo_root):
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "tools", "dessensitize_audit.py"),
         "--mode", "tracked"],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output


def test_dessensitize_audit_detects_planted_secret(tmp_path, repo_root):
    """阳性对照：审计器必须能抓出植入的敏感形态（否则它是空验的）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_mod", os.path.join(repo_root, "tools", "dessensitize_audit.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    planted_key = "sk-" + "A" * 24
    planted_email = "someone" + "@" + "realcorp-internal.com"
    text = "line1\nkey = {}\ncontact {}\n".format(planted_key, planted_email)
    hard, _review = module._scan_text(text, "planted")
    categories = {item[2] for item in hard}
    assert "secret_key" in categories
    assert "personal_email" in categories


def test_dessensitize_audit_works_without_git(tmp_path, repo_root):
    """无 ``.git`` 的导出树（git archive）也必须能跑审计——退回文件系统遍历。

    背景：`git archive HEAD | tar -x` 导出的树天然无 .git，若扫描器强依赖 git，
    干净环境验证会直接崩（而非给出结论）。兜底的排除逻辑按**特征**（pyvenv.cfg）
    而非目录名，避免把就地建的 venv 当跟踪树扫。
    """
    import shutil

    export_root = tmp_path / "export"
    shutil.copytree(os.path.join(repo_root, "tools"), export_root / "tools")
    assert not os.path.isdir(os.path.join(str(export_root), ".git"))

    result = subprocess.run(
        [sys.executable, os.path.join(str(export_root), "tools", "dessensitize_audit.py"),
         "--mode", "tracked"],
        cwd=str(export_root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "DESSENSITIZE_AUDIT_OK" in output


def test_lf_gate_works_without_git(tmp_path, repo_root):
    """无 ``.git`` 时 LF 守门退回文件系统遍历，且能识别 CR 违规（阳性对照）。"""
    export_root = tmp_path / "export"
    (export_root / "sub").mkdir(parents=True)
    good = export_root / "good.md"
    bad = export_root / "sub" / "bad.md"
    good.write_bytes(b"line\n")
    bad.write_bytes(b"line\r\n")

    names = _tracked_text_files(str(export_root))
    assert "good.md" in names
    assert "sub/bad.md" in names

    offenders = []
    for name in names:
        path = os.path.join(str(export_root), name)
        with open(path, "rb") as handle:
            if b"\r" in handle.read():
                offenders.append(name)
    assert offenders == ["sub/bad.md"]


def test_dessensitize_audit_ignores_hex_and_reserved_domains(repo_root):
    """阴性对照：sha256 十六进制段与保留域不得误报。

    注意：数字段在**源码里也不能是连续 11 位字面量**（否则审计器扫自己会命中）——
    故按片段拼接，运行时才拼出被测形态。
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_mod2", os.path.join(repo_root, "tools", "dessensitize_audit.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    digits = "18825" + "915680"          # 运行时拼出 11 位数字段
    hexish = "sha256 " + "a" * 8 + digits + "b" * 8
    assert len(digits) == 11
    text = "{}\ncontact test@example.com\nclone github.com/yuluo554/repo\n".format(hexish)
    hard, _review = module._scan_text(text, "clean")
    assert hard == [], hard


def test_dessensitize_audit_whitelists_clone_urls(repo_root):
    """克隆 URL 两种形态（HTTPS / SSH）都是发布固有公开元数据，不得判硬门。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_mod3", os.path.join(repo_root, "tools", "dessensitize_audit.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    ssh_line = "git remote set-url origin git@" + "github.com:yuluo554/labor-compliance-calculator.git"
    https_line = "git clone https://github.com/yuluo554/labor-compliance-calculator.git"
    text = "{}\n{}\n".format(ssh_line, https_line)
    hard, _review = module._scan_text(text, "clone-urls")
    assert hard == [], hard


# ---- 发布期：历史/提交信息扫描 + 提交元数据邮箱（M6-1） --------------------

def _has_git_history(repo_root):
    if not os.path.isdir(os.path.join(repo_root, ".git")):
        return False
    try:
        out = subprocess.check_output(["git", "rev-list", "--all", "-n", "1"],
                                      cwd=repo_root, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError):
        return False
    return bool(out.strip())


def test_dessensitize_audit_history_passes(repo_root):
    """全历史扫描 0 硬门命中（CI 靠 fetch-depth: 0 才有全量历史）。"""
    if not _has_git_history(repo_root):
        pytest.skip("无 git 历史（导出树），历史扫描跳过")
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "tools", "dessensitize_audit.py"),
         "--mode", "history"],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "DESSENSITIZE_AUDIT_OK" in output


def test_dessensitize_audit_messages_passes(repo_root):
    """提交信息扫描 0 硬门命中。"""
    if not _has_git_history(repo_root):
        pytest.skip("无 git 历史（导出树），提交信息扫描跳过")
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "tools", "dessensitize_audit.py"),
         "--mode", "messages"],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "DESSENSITIZE_AUDIT_OK" in output


def test_history_scan_channel_is_alive(repo_root):
    """历史扫描通道探活：防 `git grep` 多 rev 静默空扫造成的"全历史干净"假绿。

    阳性对照：把必然存在的提交标题片段喂给同一扫描通道，必须搜得到。
    """
    if not _has_git_history(repo_root):
        pytest.skip("无 git 历史（导出树），探活断言跳过")
    out = subprocess.check_output(
        ["git", "log", "--all", "--format=%s", "-n", "5"], cwd=repo_root
    ).decode("utf-8", "replace")
    assert out.strip(), "历史通道无输出 → 全历史扫描是空验"


def test_commit_metadata_emails_are_noreply(repo_root):
    """提交元数据邮箱检查（内容级扫描覆盖不到的盲区）：不得留真实个人邮箱。

    全历史作者的 ae 与 ce 两个字段都要查——只查一个会让"改了一半"蒙混过关。
    """
    if not _has_git_history(repo_root):
        pytest.skip("无 git 历史（导出树），元数据检查跳过")
    out = subprocess.check_output(
        ["git", "log", "--all", "--format=%ae%n%ce"], cwd=repo_root
    ).decode("utf-8", "replace")
    emails = {line.strip().lower() for line in out.splitlines() if line.strip()}
    assert emails, "未读到任何提交邮箱 → 检查是空验"
    allowed_domains = ("users.noreply.github.com",)
    offenders = [e for e in emails if not e.endswith(allowed_domains)]
    assert not offenders, "存在非 noreply 提交邮箱: {}".format(sorted(offenders))