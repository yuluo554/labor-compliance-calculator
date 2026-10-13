"""经济补偿 / 赔偿金引擎（plan/04 §3）——M2 实现。

公式依据（数值一律取自 ``EffectiveRuleset``，禁止硬编码）：

  1. 口径判定：解除情形 → N / N+1 / 2N / none（plan/04 §3.1 映射表）
  2. 工作年限取整：满 ``full_year_threshold_months`` 个月不满 1 年 → 按 1 年；
     不满该阈值 → 按 ``round_down_to_half_month``（plan/04 §3.2）
  3. 月工资：解除前 ``avg_wage_months`` 个月平均应得工资；
     低于 ``min_wage_monthly`` 时按最低工资（plan/04 §3.3）
  4. 三倍封顶：月工资 > 社平工资 × ``cap_multiple_of_social_avg`` 时按封顶基数，
     且年限 ≤ ``cap_years``（plan/04 §3.4）
  5. 金额：N = 基数 × 年限；N+1 = N + 代通知金；2N = 2 × N（plan/04 §3.5）
"""

from __future__ import annotations

from ..errors import NotImplementedYet

MILESTONE = "M2"

# 解除情形 → 口径（plan/04 §3.1；纯映射，无数值政策字面量）
FORMULA_BY_GROUND = {
    "mutual_agreement": "N",
    "employee_fault_dismissal": "none",
    "employer_unilateral_no_fault": "N",          # 未提前通知时由 notified 标志升级为 N+1
    "economic_layoff": "N",
    "illegal_termination": "2N",
    "contract_expiry_employer_no_renewal": "N",
    "employee_resignation_art38": "N",
    "employee_resignation_voluntary": "none",
}

FORMULA_CLAUSE_IDS = {
    "N": ["LCL-46", "LCL-47"],
    "N+1": ["LCL-40", "LCL-47"],
    "2N": ["LCL-48", "LCL-87"],
    "none": [],
}


def determine_formula(termination):
    # type: (object) -> dict
    """口径判定：解除情形 → ``{"formula", "basis", "reason"}``。

    M0 骨架仅声明接口；判定表见 :data:`FORMULA_BY_GROUND`，
    实现与基准枚举在 M2 落地（含易混边界：第 40 条未提前通知 → N+1 而非 2N）。
    """
    raise NotImplementedYet(
        "经济补偿口径判定将在 {} 实现（设计见 plan/04 §3.1）".format(MILESTONE)
    )


def compute(facts, termination, ruleset):
    # type: (object, object, object) -> dict
    """计算经济补偿/赔偿金；返回含 ``amount`` / ``steps`` / ``basis`` 的结果字典。

    实现里程碑：M2。``ruleset`` 必须是 :class:`lcc.gate.EffectiveRuleset`。
    """
    raise NotImplementedYet(
        "经济补偿引擎将在 {} 实现（公式见 plan/04 §3）".format(MILESTONE)
    )


__all__ = ["MILESTONE", "FORMULA_BY_GROUND", "FORMULA_CLAUSE_IDS", "determine_formula", "compute"]