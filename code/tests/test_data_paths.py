# -*- coding: utf-8 -*-
"""数据目录定位分支（plan/03；D-15）。"""

from __future__ import annotations

import os

import pytest

from lcc import data_paths


def test_find_data_dir_from_repo(data_dir):
    found = data_paths.find_data_dir()
    assert os.path.isdir(found)
    assert os.path.isdir(os.path.join(found, "rules"))
    assert os.path.samefile(found, data_dir)


def test_explicit_path_wins(data_dir):
    assert data_paths.find_data_dir(data_dir) == os.path.abspath(data_dir)


def test_env_var(monkeypatch, data_dir):
    monkeypatch.setenv(data_paths.ENV_VAR, data_dir)
    assert data_paths.find_data_dir() == os.path.abspath(data_dir)


def test_explicit_beats_env(monkeypatch, tmp_path, data_dir):
    other = tmp_path / "data"
    (other / "rules").mkdir(parents=True)
    monkeypatch.setenv(data_paths.ENV_VAR, data_dir)
    assert data_paths.find_data_dir(str(other)) == os.path.abspath(str(other))


def test_missing_raises(monkeypatch, tmp_path):
    monkeypatch.delenv(data_paths.ENV_VAR, raising=False)
    empty = tmp_path / "nowhere"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        data_paths.find_data_dir(str(empty))


def test_frozen_candidates_include_internal(monkeypatch, tmp_path):
    """PyInstaller 5.x 平铺 / 6.x ``_internal`` 两种布局都要覆盖。"""
    exe_dir = tmp_path / "app"
    (exe_dir / "_internal" / "data" / "rules").mkdir(parents=True)
    monkeypatch.delenv(data_paths.ENV_VAR, raising=False)
    monkeypatch.setattr(data_paths.sys, "executable", str(exe_dir / "app.exe"))
    monkeypatch.setattr(data_paths.sys, "frozen", True, raising=False)
    monkeypatch.delattr(data_paths.sys, "_MEIPASS", raising=False)
    found = data_paths.find_data_dir()
    assert os.path.samefile(found, str(exe_dir / "_internal" / "data"))