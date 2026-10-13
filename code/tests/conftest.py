# -*- coding: utf-8 -*-
"""pytest 全局配置：把 ``code/src`` 加入导入路径（未安装也可跑），并提供共用夹具。"""

from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(CODE_DIR)
SRC_DIR = os.path.join(CODE_DIR, "src")

for path in (SRC_DIR,):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(scope="session")
def repo_root():
    # type: () -> str
    return REPO_ROOT


@pytest.fixture(scope="session")
def data_dir():
    # type: () -> str
    return os.path.join(REPO_ROOT, "data")