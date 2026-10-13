# -*- coding: utf-8 -*-
"""CLI 退出码语义（plan/03 §六；D-14）——**锁进测试，后续重构不得漂移**。

退出码：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误。
"""

from __future__ import annotations

import json
import os

import pytest

from lcc import cli
from lcc.errors import EXIT_DEGRADED, EXIT_INPUT_ERROR, EXIT_OK


def test_exit_code_constants():
    assert (EXIT_OK, EXIT_DEGRADED, EXIT_INPUT_ERROR) == (0, 1, 2)


def test_no_command_returns_input_error():
    assert cli.main([]) == EXIT_INPUT_ERROR


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "lcc" in capsys.readouterr().out


def test_params_command_ok(data_dir, capsys):
    assert cli.main(["--data-dir", data_dir, "params"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "规则包" in out
    assert "310000" in out
    assert "待核对" in out


def test_doctor_command_ok(data_dir, capsys):
    assert cli.main(["--data-dir", data_dir, "doctor"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "条款库" in out
    assert "自检结论" in out


def test_calc_missing_file_returns_input_error(data_dir, tmp_path):
    missing = str(tmp_path / "nope.json")
    assert cli.main(["--data-dir", data_dir, "calc", missing]) == EXIT_INPUT_ERROR


def test_calc_bad_json_returns_input_error(data_dir, tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert cli.main(["--data-dir", data_dir, "calc", str(path)]) == EXIT_INPUT_ERROR
    assert "解析失败" in capsys.readouterr().err


def test_calc_bad_input_schema_returns_input_error(data_dir, tmp_path, capsys):
    path = tmp_path / "bad2.json"
    path.write_text(json.dumps({"employment": {"year": 2026}}), encoding="utf-8")
    assert cli.main(["--data-dir", data_dir, "calc", str(path)]) == EXIT_INPUT_ERROR
    assert "region_code" in capsys.readouterr().err


def test_calc_unknown_coordinate_returns_input_error(data_dir, tmp_path, capsys):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({
        "employment": {"region_code": "999999", "year": 2026, "hire_date": "2020-01-01"}
    }), encoding="utf-8")
    assert cli.main(["--data-dir", data_dir, "calc", str(path)]) == EXIT_INPUT_ERROR
    assert "999999" in capsys.readouterr().err


def test_calc_gate_blocked_returns_input_error(data_dir, tmp_path, capsys):
    """未核对参数包（广东仍 pending）→ 门控拦截 exit 2（核心纪律的可执行证据）。"""
    path = tmp_path / "d.json"
    path.write_text(json.dumps({
        "employment": {"region_code": "440000", "year": 2026, "hire_date": "2020-01-01"},
        "termination": {"ground": "mutual_agreement"},
    }), encoding="utf-8")
    assert cli.main(["--data-dir", data_dir, "calc", str(path)]) == EXIT_INPUT_ERROR
    assert "未核对" in capsys.readouterr().err


def test_calc_verified_coordinate_passes_gate_into_engine(data_dir, tmp_path, capsys):
    """已核对坐标（北京 2025）→ 门控放行进入引擎。

    M3 后：四模块全部实现，默认四模块与单跑 ``severance`` 都应成功（exit 0 并
    给出金额）；两条通路一起断言，防止"门控放行"与"引擎实现"两个事实互相掩盖。
    """
    path = tmp_path / "verified.json"
    path.write_text(json.dumps({
        "employment": {"region_code": "110000", "year": 2025, "hire_date": "2020-01-01",
                       "terminate_date": "2025-06-30",
                       "monthly_wages": ["12000.00"] * 12},
        "termination": {"ground": "mutual_agreement"},
    }), encoding="utf-8")

    # 只跑经济补偿 → 成功出金额
    code = cli.main(["--data-dir", data_dir, "calc", str(path), "--modules", "severance"])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "经济补偿" in out

    # 默认四模块 → M3 全部实现，成功出四模块结论
    code = cli.main(["--data-dir", data_dir, "calc", str(path)])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "经济补偿/赔偿金" in out
    assert "加班费" in out
    assert "未休年休假折算" in out
    assert "未签书面劳动合同二倍工资" in out


def test_calc_real_truth_record_passes_gate(data_dir, tmp_path, capsys):
    """真值库中的真实记录（已核对坐标）走完整通路：门控放行 + M2 经济补偿可算。

    真值库记录 → 抽出 input_facts 写单条 → 坐标加载 → 门控放行 → 经济补偿引擎出金额。
    与 pending 坐标（exit 2）形成对照；证明门控对已核对坐标确实放通。
    """
    truth_path = os.path.join(data_dir, "truth", "cases-boundary.json")
    with open(truth_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)["cases"][0]
    assert tuple(record["coordinate"]) in (
        ("110000", 2025), ("110000", 2026), ("310000", 2025), ("310000", 2026))

    path = tmp_path / "record.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    code = cli.main(["--data-dir", data_dir, "calc", str(path), "--modules", "severance"])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "经济补偿" in out


def test_calc_severance_amount_matches_truth_record(data_dir, tmp_path, capsys):
    """端到端金额对账：CLI 输出的经济补偿金额 = 真值库该记录 ``expected.severance.amount``。"""
    truth_path = os.path.join(data_dir, "truth", "cases-boundary.json")
    with open(truth_path, "r", encoding="utf-8") as handle:
        record = json.load(handle)["cases"][0]
    expected_amount = record["expected"]["severance"]["amount"]

    path = tmp_path / "record.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    code = cli.main(["--data-dir", data_dir, "calc", str(path), "--modules", "severance"])
    out = capsys.readouterr().out
    assert code == EXIT_OK
    assert "{} 元".format(expected_amount) in out, out


def test_calc_preview_returns_degraded(data_dir, tmp_path, capsys):
    """预览模式：门控命中时仅展示参数元信息，**不进入引擎**、不输出金额 → exit 1。

    这是 plan/03 §六 / plan/04 §八 的降级语义（`allow_pending` 通路不得产出金额）。
    """
    path = tmp_path / "e.json"
    path.write_text(json.dumps({
        "employment": {"region_code": "440000", "year": 2026, "hire_date": "2020-01-01"},
        "termination": {"ground": "mutual_agreement"},
    }), encoding="utf-8")
    code = cli.main(["--data-dir", data_dir, "calc", "--preview", str(path)])
    out = capsys.readouterr().out
    assert code == EXIT_DEGRADED
    assert "参数来源" in out
    assert "预览模式" in out
    assert "经济补偿/赔偿金" not in out, "预览模式不得输出任何金额结论"


def test_calc_accepts_truth_record_input(data_dir, tmp_path):
    """数据文件 ≠ 命令输入：带 input_facts 包装的真值记录要能直接喂。"""
    path = tmp_path / "record.json"
    path.write_text(json.dumps({
        "case_id": "demo-001",
        "input_facts": {
            "employment": {"region_code": "310000", "year": 2026, "hire_date": "2020-01-01"},
            "termination": {"ground": "mutual_agreement"},
        },
        "expected": {"formula": "N"},
    }), encoding="utf-8")
    assert cli.main(["--data-dir", data_dir, "calc", "--preview", str(path)]) == EXIT_DEGRADED


def test_gui_without_pyside_returns_input_error(data_dir, capsys, monkeypatch):
    """PySide6 缺失时：打印安装提示并 exit 2（不崩溃）。"""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("No module named 'PySide6'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert cli.main(["--data-dir", data_dir, "gui"]) == EXIT_INPUT_ERROR
    assert "PySide6" in capsys.readouterr().out


def test_ensure_utf8_stdio_reconfigures_cp1252():
    """编码守卫：cp1252 流必须被 reconfigure（NFR-8；CI windows 崩溃的根因）。"""
    import io
    import sys as _sys

    from lcc import _stdio

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    original = _sys.stdout
    _sys.stdout = stream
    try:
        _stdio._ensure_utf8_stdio(("stdout",))
        assert stream.encoding.lower().replace("-", "") == "utf8"
    finally:
        _sys.stdout = original


def test_ensure_utf8_stdio_keeps_cp936():
    """中文控制台（cp936）能编码中文 → 不应被改动。"""
    import io
    import sys as _sys

    from lcc import _stdio

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp936", errors="strict")
    original = _sys.stdout
    _sys.stdout = stream
    try:
        _stdio._ensure_utf8_stdio(("stdout",))
        assert stream.encoding.lower() in ("cp936", "gbk")
    finally:
        _sys.stdout = original