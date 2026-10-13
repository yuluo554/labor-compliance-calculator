# -*- coding: utf-8 -*-
"""内置基准守门（M2 起；plan/05 §二、DoD M2-1~M2-3）。

基准脚本 ``tools/bench.py`` 的语义锁进测试，防止后续改动悄悄降标：
  * B1 口径判定（9 种情形枚举）通过率 100%；
  * B2 封顶与取整边界（真值库全量经引擎重算）全通过；
  * B3 参数库非法组合拦截率 100%（含阳性对照，防"什么都拦"的空验）；
  * 退出码 0 达标 / 1 未达标（锁进测试）。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest


def _load_bench(repo_root):
    # type: (str) -> object
    path = os.path.join(repo_root, "tools", "bench.py")
    spec = importlib.util.spec_from_file_location("bench_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bench(repo_root):
    return _load_bench(repo_root)


def test_b1_formula_determination_is_100_percent(bench):
    result = bench.run_b1()
    assert result["total"] >= 9, "口径判定情形枚举不足 9 种"
    assert result["passed"] == result["total"], result["failures"]
    assert result["rate"] == 1.0


def test_b1_covers_every_model_ground(bench):
    """基准必须覆盖模型声明的每一种解除情形（防新增枚举后基准静默漏测）。"""
    from lcc.model import TERMINATION_GROUNDS

    covered = {ground for ground, _notified in bench.EXPECTED_FORMULA}
    assert covered == set(TERMINATION_GROUNDS)


def test_b2_boundary_reconciles_all_truth_cases(bench):
    result = bench.run_b2()
    assert result["total"] >= 400, result["total"]
    assert result["passed"] == result["total"], result["failures"][:3]


def test_b3_interception_is_100_percent(bench):
    result = bench.run_b3()
    assert result["total"] >= 4
    assert result["passed"] == result["total"], result["failures"]


def test_b3_positive_control_verified_coordinates_pass(bench):
    """阳性对照：已核对坐标必须放行（否则"拦截率 100%"只是"什么都拦"）。"""
    result = bench.run_positive_control()
    assert result["passed"] == result["total"], result["failures"]
    assert result["total"] >= 4


def test_bench_exit_code_zero_when_all_pass(repo_root):
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "tools", "bench.py")],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = result.stdout.decode("utf-8", "replace")
    assert result.returncode == 0, output
    assert "全部达标" in output


def test_bench_reports_below_target_as_exit_one(bench, monkeypatch):
    """未达标 → exit 1（锁进测试：基准不得"永远绿"）。"""
    failing = {
        "name": "B1 口径判定", "passed": 0, "total": 1,
        "target": "100%", "rate": 0.0, "ok": False, "failures": [("demo",)],
    }
    monkeypatch.setattr(bench, "BENCHMARKS", (lambda: failing,))
    assert bench.main([]) == bench.EXIT_BELOW_TARGET


def test_bench_is_offline_and_fast(repo_root):
    """全离线：基准不得 import 网络/第三方库；单次全量 < 5 秒（宽松上限）。"""
    import time

    bench_path = os.path.join(repo_root, "tools", "bench.py")
    with open(bench_path, "r", encoding="utf-8") as handle:
        text = handle.read()
    for token in ("urllib", "requests", "http.client", "socket"):
        assert token not in text, "基准不得引入网络依赖: {}".format(token)

    start = time.time()
    subprocess.run(
        [sys.executable, bench_path], cwd=repo_root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    assert time.time() - start < 5.0
