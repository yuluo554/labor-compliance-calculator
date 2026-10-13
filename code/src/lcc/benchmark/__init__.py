"""基准与真值语义（plan/05 §二：M4 落地，M1 起建接口）。

本包承载**合成雇佣档案真值的唯一实现源**（:mod:`lcc.benchmark.cases`）：
生成器（``tools/gen_cases.py``）、测试与基准共用同一语义，**不得改真值凑引擎**。

纪律：本目录受零政策字面量门禁扫描（``tools/check_no_literals.py``）——全部法定数值
必须经 :class:`~lcc.gate.EffectiveRuleset` 从 ``data/constants`` 与 ``data/rules`` 取，
不得在本目录内联。
"""

from __future__ import annotations

__all__ = []
