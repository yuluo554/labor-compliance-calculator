"""计算引擎层：纯函数、Decimal、零 IO、零第三方依赖。

四个引擎模块在 M0 骨架阶段仅声明 API 面（函数签名 + 公式依据），
具体实现在 M2（经济补偿）/ M3（其余三引擎）落地。
调用未实现通路一律抛 :class:`~lcc.errors.NotImplementedYet`（exit 1），
由 CLI 捕获并给出里程碑提示，**不静默返回错误结果**。

纪律：引擎函数只接受 :class:`lcc.gate.EffectiveRuleset`（门控产物），
不接受裸 dict/Ruleset；引擎层不得 import CLI/GUI（AST 守门测试断言）。
"""

from __future__ import annotations

from . import annual_leave, double_wage, overtime, severance

__all__ = ["severance", "overtime", "annual_leave", "double_wage"]