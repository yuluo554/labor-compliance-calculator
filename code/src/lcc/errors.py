"""异常体系与 CLI 退出码映射。

退出码语义（plan/04 §8，锁进 code/tests/test_cli_exit_codes.py）：
  0 = 计算成功
  1 = 降级完成 / 条款缺失 / 计算非法状态 / 引擎未实现
  2 = 输入格式错 / 参数坐标错 / status 门控拦截（未核对）
"""

from __future__ import annotations

EXIT_OK = 0
EXIT_DEGRADED = 1
EXIT_INPUT_ERROR = 2


class LccError(Exception):
    """本项目异常基类：携带退出码与可选的明细列表。"""

    exit_code = EXIT_DEGRADED

    def __init__(self, message, details=None):
        # type: (str, object) -> None
        super().__init__(message)
        self.message = message
        self.details = list(details or [])

    def render(self):
        # type: () -> str
        lines = [self.message]
        for item in self.details:
            lines.append("  - {}".format(item))
        return "\n".join(lines)

    def __str__(self):
        # type: () -> str
        return self.render()


class InputError(LccError):
    """输入事实缺失/格式错/字段非法。"""

    exit_code = EXIT_INPUT_ERROR


class ParamCoordinateError(LccError):
    """请求的 (地区, 年度) 无对应参数包，或参数包坐标与请求不一致。"""

    exit_code = EXIT_INPUT_ERROR


class ParamSchemaError(LccError):
    """参数包/常数包不符合 schema（含缺来源、文件名与内部坐标不一致）。"""

    exit_code = EXIT_INPUT_ERROR


class GateError(LccError):
    """status 门控拦截：命中未核对（pending）条目，不得进入计算路径。"""

    exit_code = EXIT_INPUT_ERROR


class LawBasisError(LccError):
    """结论引用的条款 id 在条款库中不存在。"""

    exit_code = EXIT_DEGRADED


class ComputationError(LccError):
    """计算过程中的非法状态（负工资、日期区间倒置等）。"""

    exit_code = EXIT_DEGRADED


class NotImplementedYet(LccError):
    """里程碑尚未实现的通路（骨架阶段占位，明确提示而非静默错误）。"""

    exit_code = EXIT_DEGRADED


class OptionalDependencyError(LccError):
    """可选依赖缺失（如 XLSX 导出需要 ``openpyxl``）。

    按降级语义给 exit 1：调用方应回退到不依赖该依赖的通路（Markdown）并提示，
    而不是崩溃或静默产出半成品。
    """

    exit_code = EXIT_DEGRADED


__all__ = [
    "EXIT_OK",
    "EXIT_DEGRADED",
    "EXIT_INPUT_ERROR",
    "LccError",
    "InputError",
    "ParamCoordinateError",
    "ParamSchemaError",
    "GateError",
    "LawBasisError",
    "ComputationError",
    "NotImplementedYet",
    "OptionalDependencyError",
]