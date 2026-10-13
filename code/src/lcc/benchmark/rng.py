"""自研 SplitMix64 伪随机数（plan/05 §1.3、§1.4）。

**为什么不用 stdlib ``random``**：

* 跨 Python 版本/实现，``random`` 的算法与种子派生策略可能变化 → 冻结产物的
  「再生成逐字节一致」无法跨版本保证；
* 本项目需要**显式、可审计、可复现**的序列：算法固定（SplitMix64）、种子固定、
  状态由调用方持有，源码里能一眼看出取值来源。

SplitMix64 是公有领域算法（Steele/Lea/Flood 2014），此处按 64 位掩码自行实现，
不使用任何第三方或 stdlib 随机设施。
"""

from __future__ import annotations

_MASK = (1 << 64) - 1
_GOLDEN_GAMMA = 0x9E3779B97F4A7C15
_MIX_A = 0xBF58476D1CE4E5B9
_MIX_B = 0x94D049BB133111EB


class SplitMix64(object):
    """确定性 64 位伪随机数发生器（显式状态、无全局种子）。"""

    __slots__ = ("_state",)

    def __init__(self, seed):
        # type: (int) -> None
        self._state = int(seed) & _MASK

    @property
    def state(self):
        # type: () -> int
        return self._state

    def next_u64(self):
        # type: () -> int
        self._state = (self._state + _GOLDEN_GAMMA) & _MASK
        z = self._state
        z = ((z ^ (z >> 30)) * _MIX_A) & _MASK
        z = ((z ^ (z >> 27)) * _MIX_B) & _MASK
        return (z ^ (z >> 31)) & _MASK

    def next_below(self, bound):
        # type: (int) -> int
        """返回 ``[0, bound)`` 内的整数；``bound <= 0`` 报错（避免静默取模）。"""
        if bound <= 0:
            raise ValueError("bound 必须为正整数，得到 {!r}".format(bound))
        return self.next_u64() % bound

    def next_int(self, low, high):
        # type: (int, int) -> int
        """返回 ``[low, high]`` 闭区间内的整数。"""
        if high < low:
            raise ValueError("high({}) 不得小于 low({})".format(high, low))
        return low + self.next_below(high - low + 1)

    def __repr__(self):
        # type: () -> str
        return "SplitMix64(state=0x{:016X})".format(self._state)


__all__ = ["SplitMix64"]
