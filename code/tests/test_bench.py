# -*- coding: utf-8 -*-
"""内置基准守门（M2 起；plan/05 §二、DoD M2-1~M2-3、M4-1~M4-4）。

基准脚本 ``tools/bench.py`` 的语义锁进测试，防止后续改动悄悄降标：
  * B1 口径判定（9 种情形枚举）通过率 100%；
  * B2 全模块对账（真值库全量经四引擎重算）全通过；
  * B3 参数库非法组合拦截率 100%（含阳性对照，防"什么都拦"的空验）；
  * B4 参数推导边界扫描（不依赖真值库样本，±0.01 邻域）全通过；
  * B5 双向对账（公式推导 vs 穷举恢复）全通过；
  * 退出码 0 达标 / 1 未达标 / 2 用法错误（锁进测试）。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from decimal import Decimal

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


def test_b2_covers_all_four_modules(bench):
    """B2 覆盖面必须含四模块（M3 起 B2 由只跑 severance 扩到四引擎全模块对账）。"""
    from lcc.benchmark import cases as truth

    assert bench.truth.MODULES == ("severance", "overtime", "annual_leave", "double_wage")
    # 逐模块调用一次，任一模块缺失即在 _engine_output 处报错
    result = bench.run_b2()
    assert result["ok"], result["failures"][:3]


# ---- M4-2：B4 参数推导边界扫描（不依赖真值库样本） ------------------------

def test_b4_parameter_derived_boundary_scan_passes(bench):
    """B4：切换端点全部由参数包推出，±0.01 邻域断言，全通过。"""
    result = bench.run_b4()
    assert result["total"] >= 40, result["total"]
    assert result["passed"] == result["total"], result["failures"][:5]


def test_b4_covers_every_verified_coordinate(bench):
    """B4 扫描面必须覆盖全部已核对坐标（否则某坐标的边界从未被断言）。"""
    from lcc.params import load_ruleset

    assert len(bench.VERIFIED_COORDINATES) >= 4
    for region, year in bench.VERIFIED_COORDINATES:
        load_ruleset(region, year, data_dir=bench.DATA_DIR)  # 坐标必须真实存在


def test_b4_does_not_read_truth_library(bench, monkeypatch):
    """B4 是**规则驱动**而非样本驱动：临时清空真值库后仍须全通过。"""
    monkeypatch.setattr(bench, "_load_cases", lambda profile: [])
    result = bench.run_b4()
    assert result["ok"], result["failures"][:5]


def test_b4_detects_cap_switch_drift(bench, monkeypatch):
    """阳性对照：把封顶比较从「严格大于」改成「大于等于」→ B4 必须报失败。

    防止 B4 成为空验（只跑通、抓不住语义漂移）。
    """
    from lcc.engine import severance

    original = severance.compute

    def drifted_cap(facts, termination, ruleset):
        # 漂移：恰好等于封顶基数也判为封顶（应为严格大于）
        output = original(facts, termination, ruleset)
        cap_base = ruleset.social_avg_wage_monthly() * ruleset.severance_cap_multiple()
        if Decimal(output["monthly_wage_avg"]) >= cap_base and not output["cap_applied"]:
            output["cap_applied"] = True
        return output

    monkeypatch.setattr(severance, "compute", drifted_cap)
    result = bench.run_b4()
    assert not result["ok"], "B4 未捕获封顶切换点漂移（空验）"


# ---- M4-3：B5 双向对账（公式推导 vs 穷举恢复） -----------------------------

def test_b5_bidirectional_reconciliation_passes(bench):
    """B5：公式推导端点与穷举恢复切换点两条独立路径互验，全通过。"""
    result = bench.run_b5()
    assert result["total"] >= 20, result["total"]
    assert result["passed"] == result["total"], result["failures"][:5]


def test_b5_detects_year_rounding_drift(bench, monkeypatch):
    """阳性对照：把年限阈值比较从「≥」改成「>」→ B5 必须报失败（防空验）。"""
    from lcc.engine import severance

    _ROUND_FLOOR = "ROUND_FLOOR"

    def drifted_years(hire_date, terminate_date, ruleset):
        months, remainder = severance._months_and_remainder(hire_date, terminate_date)
        service_months = Decimal(months)
        if remainder >= 15:
            service_months += Decimal("0.5")
        full_years = (service_months / Decimal(12)).to_integral_value(rounding=_ROUND_FLOOR)
        rem_months = service_months - full_years * Decimal(12)
        # 漂移点：应为 >=，此处改为 >
        if rem_months > ruleset.full_year_threshold_months():
            return full_years + ruleset.round_up_to_year()
        if rem_months > 0:
            return full_years + ruleset.round_down_to_half_month()
        return full_years

    monkeypatch.setattr(severance, "service_years_for_compensation", drifted_years)
    result = bench.run_b5()
    assert not result["ok"], "B5 未捕获年限取整漂移（空验）"


def test_b5_does_not_read_truth_library(bench, monkeypatch):
    """B5 同样是规则驱动：清空真值库后仍须全通过。"""
    monkeypatch.setattr(bench, "_load_cases", lambda profile: [])
    result = bench.run_b5()
    assert result["ok"], result["failures"][:5]


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


def test_bench_unknown_only_is_exit_usage(bench, capsys):
    """用法错误（--only 未知基准名）→ exit 2（EXIT_USAGE 通路锁进测试，M4-4）。"""
    assert bench.main(["--only", "NOPE"]) == bench.EXIT_USAGE
    assert "用法错误" in capsys.readouterr().err


def test_bench_only_runs_selected_benchmark(bench, monkeypatch):
    """``--only`` 只跑选中的基准（其余不执行）——用哨兵确认未越界。"""
    called = []

    def sentinel():
        called.append(True)
        return {"name": "sentinel", "passed": 1, "total": 1, "target": "100%",
                "rate": 1.0, "ok": True, "failures": []}

    monkeypatch.setitem(bench._BENCHMARK_KEYS, "B4", sentinel)
    assert bench.main(["--only", "B4"]) == bench.EXIT_OK
    assert called == [True]


def test_bench_exit_codes_are_0_1_2(bench):
    """三退出码语义齐备（0 达标 / 1 未达标 / 2 用法错误）。"""
    assert (bench.EXIT_OK, bench.EXIT_BELOW_TARGET, bench.EXIT_USAGE) == (0, 1, 2)


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
