#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PyInstaller 打包入口：CLI 控制台 exe（D-19）。

独立入口脚本（而非直接指向 ``lcc/__main__.py``）的原因：PyInstaller 需要一个
**顶层脚本**做依赖分析起点；指向包内模块会把包路径混进分析结果。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code", "src"))

from lcc.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
