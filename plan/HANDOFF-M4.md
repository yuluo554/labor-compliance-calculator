# HANDOFF-M4：M3 三引擎 → M4 基准完善

> 交接快照（ai-tool-project-sprint 阶段 0）。**新对话续接用法**：
> `/goal 读取 "plan/HANDOFF-M4.md" 继续完成任务`（入库文件内一律写相对路径）。
> 快照日期：2026-10-13 ｜ 上一里程碑：**M3 加班费/年休假/二倍工资** ｜ 下一棒：**M4 基准完善**

---

## 一、当前进度（M3 已完成什么）

### 1.1 三引擎落地

| # | 能力 | 实现要点 | 证据 |
|---|---|---|---|
| M3-1 | 加班费引擎 `engine/overtime.py` | 日历四类联动（`ruleset.holiday_day_type`）→ 常数包三档倍率；基数 = 月平均应得工资（D-33，不低于最低工资）÷（`monthly_pay_days` × `overtime.standard_daily_hours`）；显式 `kind` 覆盖日历；`work_system` 为记录性字段（R-03 闭环 D-41） | 全量 406 条对账 **0 mismatch**；`test_overtime_day_type_rate_mapping_matches_calendar` 等 7 项 |
| M3-2 | 年休假引擎 `engine/annual_leave.py` | 分档（`entitlement_tiers`）+ 当年度折算（`days_per_year`）+ 向下取整（R-02/D-31）+ 冲抵（`unused_multiple` − `already_paid_portion`）；累计不满 1 年 → 应休 0 天 | 全量 406 条 **0 mismatch**；`test_annual_leave_*` 6 项 |
| M3-3 | 二倍工资引擎 `engine/double_wage.py` | 起算（满 `start_after_months` 个月次日，月末夹取）+ 上限（`max_months`）+ 差额倍数（`difference_multiple`）+ 逐月明细；已签合同 → 0 | 全量 406 条 **0 mismatch**；`test_double_wage_*` 5 项 |
| M3-4 | 三引擎挂依据 + 对账 | 挂 `LL-44/36`、`ALR-3/5`+`MOHRSS-ORDER-1-ART10/11/12`、`LCL-82`；依据 id 全部可解析 | `test_m3_engines_basis_ids_all_resolvable`；`test_m3_engines_reconcile_all_truth_cases` |
| M3-5 | 基准 B2 扩到四模块 | `tools/bench.py` 的 B2 由「只跑 severance」扩为**四引擎全模块**对账（更名「B2 边界与全模块对账」） | B2 **406/406**；`test_b2_covers_all_four_modules` |

**引擎输出字段**（对账/报告用）：

- `overtime`: `{hourly_base, min_wage_applied, entries:[{date, day_type, rate, hours, entry_amount, day_type_source}], total, amount, work_system, steps, basis}`
- `annual_leave`: `{entitlement_days, prorated_days, taken_days, unused_days, daily_wage, monthly_wage, payable_total, already_paid, additional_due, amount, steps, basis}`
- `double_wage`: `{signed, start_date, end_date, months, monthly_wage, monthly_detail, total_difference, amount, steps, basis}`

### 1.2 一处真值语义同源修正（D-42，**未动冻结真值**）

`benchmark/cases.py::annual_leave_expected` 与 `engine/annual_leave.py` 对「累计工作年限未落入任何分档」的处理：原真值语义抛 `ValueError`。经查，**累计不满 1 年依法不享受年休假**（《职工带薪年休假条例》第三条享受条件）→ 正确口径是**应休 0 天**，而非报错。两处**同源修正**为返回 `0` 天，避免出现"第二份语义"。真值库不含该区间（最小分档 1 年），故 `expected`/`also_expect`/`input_facts` 不变 → `tools/gen_cases.py --check` 仍 `FROZEN_TRUTH_OK`（406 条逐字节一致）。决策留档：plan/06 **D-42**。

### 1.3 M3 完成判据（已实测达成）

> 真值库 406 条中 `overtime`/`annual_leave`/`double_wage` 三模块全部对账 0 mismatch；`tools/bench.py` 全达标。

实测：

```
$ py -X utf8 tools/bench.py
[OK]   B1 口径判定: 9/9（目标 100%）
[OK]   B2 边界与全模块对账: 406/406（目标 全通过）
[OK]   B3 参数库自洽（拦截率）: 5/5（目标 100%）
[OK]   阳性对照（已核对坐标放行）: 4/4（目标 全通过）
基准结论：全部达标
```

### 1.4 验证证据（M3 收尾实跑）

- 全量 pytest：**168 passed**（本机 3.8.8 与 3.12.10 双验，收集数一致）。
- 五道门禁：`NO_POLICY_LITERALS_OK`（11 文件 0 命中）/ `FROZEN_RULESETS_OK` / `FROZEN_TRUTH_OK` / `DESSENSITIZE_AUDIT_OK`（tracked + messages）。
- CLI 冒烟：`params` / `doctor` exit 0；`calc --modules severance` exit 0；**`calc`（默认四模块）exit 0 并出四模块金额**；`calc --preview` exit 1 且不输出金额。
- 基准全达标（见 §1.3）。

### 1.5 CI

- M3 提交推送 `origin/main` 后须**复核 CI 三矩阵全绿**（ubuntu/py3.12 + windows/py3.12 + windows/py3.8），CLI smoke 步骤已新增 `python -m lcc calc examples/sample-case.json`（默认四模块）。
- push 事件数 = run 数（`git rev-list --count` 数的是提交数，勿混用）。

---

## 二、M4 待办（下一棒做什么）

| # | 任务 | 关键点 |
|---|---|---|
| M4-1 | B1/B2/B3 三类基准全量跑通，指标进 README | ✅ 已在 M2/M3 达成（B2 现已含四模块）；README 评测表已更新为 M3 实测 |
| M4-2 | 边界自洽扫描（规则表推导 + ±0.01 邻域）全通过 | **未做**：当前 B2 是"真值库记录重算对账"；M4 需补"规则表/参数推导出的边界点"扫描（不依赖真值库样本） |
| M4-3 | 双向对账（公式推导 vs 穷举恢复）一致 | **未做**：如年休假分档边界、加班倍率档位、二倍工资月数区间穷举 |
| M4-4 | `tools/bench.py` 退出码 0/1/2 语义锁进测试 | 部分已锁（`test_bench_reports_below_target_as_exit_one`）；`EXIT_USAGE=2` 通路待补断言 |

> **M4 完成判据（建议）**：B2 边界扫描覆盖"参数推导边界"（不靠真值库样本）且 0 失败；双向对账一致；`tools/bench.py` 三退出码语义均有测试。

---

## 三、既定口径清单（动了会打挂基准/测试的约定）

1. **真值语义**：`expected` 主期望 + `also_expect` 隐含结论；对账按"全部非 pass 字段集"；语义**单一实现源** `lcc/benchmark/cases.py`。
2. **不许改真值凑引擎**：发现口径错误改引擎 + 加测试。**但检查器谓词自身不自洽**时，可改谓词（不动冻结产物）——M2 的 D-39 即此例；**真值语义本身的口径错误**须**引擎与真值同源修正**（M3 的 D-42 即此例，<1 年应休 0）。判据均为 `gen_cases.py --check` 仍 `FROZEN_TRUTH_OK`。
3. **Decimal 口径**：JSON `parse_float=Decimal`；金额量化两位 `ROUND_HALF_UP`；天数记录精度 6 位。已定稿取整方向：年休假应休未休天数**向下取整**（R-02，D-31）；年限余日 ≥15 天计 0.5 月（D-34）。
4. **status 门控单点**：只有 `gate.effective_ruleset()` 产出可计算规则集；引擎签名只接受 `EffectiveRuleset`。
5. **坐标精确匹配**：`load_ruleset` 不做模糊/回退；跨坐标必须报错。
6. **零政策字面量**：法定数值只来自数据包；`tools/check_no_literals.py` 扫描 engine/benchmark/gui/pipeline（含 docstring/注释）。**新增引擎代码前先看该脚本的 `BANNED_TOKENS`**（当前禁用：21.75 / 365 / 150·200·300 及其百分号形态 / 1.5·2.0·3.0）。**注意**：docstring 里写"150%/200%/300%"会命中——M3 已改为"最高/次之/最低档"描述。
7. **退出码**：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误；`--preview` 命中门控 → exit 1 且不进入引擎。
8. **测试全离线**：零网络、零 API、无外部 mock。
9. **冻结产物纪律**：`data/rules/*` 与 `data/truth/*` 均为生成器产出，**禁手改**；文本 `write_bytes` + `\n`。
10. **引擎层不得 import CLI/GUI**；核心层零第三方依赖。
11. **日历唯一来源**：日期类型判定只在 `ruleset.holiday_day_type()`（四类），引擎不得自建日历逻辑。
12. **引擎输出含 `amount`**：四引擎输出均含 `amount` 字段（金额结论），CLI/报告据此判定"有无金额"。

### 三.1 月工资口径（D-32）

`monthly_wages` 单序列同时服务经济补偿/年休假/加班费/二倍工资，约定为**「应得工资、剔除加班工资」**。

### 三.2 加班基数与工时制度（D-33 / D-41）

- 加班基数 = 劳动者月工资（12 个月平均，不低于最低工资），**地区无关**。
- 倍率**一律由日历日期类型 + 常数包**决定，**不随 `work_system` 变化**（R-03 闭环 D-41）；`work_system` 为记录性字段；不定时工作制的地区例外留待逐地区参数化。

### 三.3 日历三字段

`holiday_calendar` 三字段：`days`（法定节假日，最高档）/ `rest_days`（调休休息日，次档）/ `adjusted_workdays`（调休上班日，次档）；其余为 `workday`（最低档）。缺 `rest_days` 会系统性少算（D-37）。

### 三.4 年休假取整（D-31）

取整方向 = **向下取整**，作用于**「应休未休天数」最终量**（`floor(折算应休天数 − 当年度已安排天数)`），下限截 0；折算应休天数本身保留原值。**累计不满 1 年 → 应休 0 天**（D-42）。

### 三.5 二倍工资区间（plan/04 §6）

起算 = 用工满 `start_after_months` 个月的**次日**（月末夹取）；硬性截止 = 用工满 `start_after_months + max_months` 个月之日；区间月数 = `_months_and_remainder(start, end)[0] + 1`（首尾含当月）；`end < start` → 0 个月。

---

## 四、本机环境坑（全部实测）

- **本机有 3.8.8 与 3.12.10**（`py -0p`）：3.8 上 `pytest` 解析到 **8.3.5**；**别把"本机 3.12 能跑"当 3.8 证据**。M3 已双验 168 passed。
- **`py -X utf8` 是本机习惯、也是 CI 盲区**：入口 `_ensure_utf8_stdio()` 是必需品。
- **pyc 偶发损坏 / 退出期 segfault**：全程 `PYTHONDONTWRITEBYTECODE=1`；若见 pytest 全绿但退出码 139，先 `find . -name __pycache__ -prune -exec rm -rf {} +` 再跑。
- **Git Bash `/tmp` ≠ Python 的 `/tmp`**：给 CLI 传文件路径时用**仓库内相对路径**（如 `.scratch/x.json`），不要用 `/tmp`。
- **`--modules` 是 `nargs="+"`**：位置参数 `input` 必须写在 `--modules` **之前**（`lcc calc <input> --modules severance`）。
- **pip 代理污染**：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- **venv 通道**：Git Bash 下用 `./.venv/Scripts/python.exe` 相对形式；`py` 启动器会绕过 venv。
- **数据目录显式传入不参与回退**（给错即报错）——刻意的，防假绿。

---

## 五、DoD 逐项核对（M3）

| # | DoD | 状态 | 证据 |
|---|---|---|---|
| M3-1 | 加班费：工时制度区分 + 三档倍数 + 日历联动，基准通过 | ✅ | 日历四类联动；三档取常数包；406/406；`test_overtime_*` |
| M3-2 | 年休假：分档 + 折算 + 冲抵（300% 含 100%），边界基准通过 | ✅ | 分档 1/10/20；向下取整 D-31；冲抵；406/406；`test_annual_leave_*` |
| M3-3 | 二倍工资：起算（第 29/30/31 天）+ 上限（11 个月）+ 逐月明细，边界基准通过 | ✅ | 满一个月次日；11 个月上限；逐月明细；406/406；`test_double_wage_*` |
| M3-4 | 三引擎均挂依据条款；条款缺失时 exit 1 | ✅ | 挂 `LL-44/36`、`ALR-3/5`+`MOHRSS-ORDER-1-ART10/11/12`、`LCL-82`；依据 id 全可解析 |
| M3-5 | 基准 B2 覆盖面扩到三模块；指标进 README 评测表 | ✅ | B2 四模块 406/406；README 评测表更新为 M3 实测 |

**偏差说明**：M3 期间对年休假"累计不满 1 年"口径做了**引擎 + 真值语义同源修正**（D-42，未动冻结真值，`FROZEN_TRUTH_OK` 保持）；工时制度区分在 v1 落为记录性字段（R-03 闭环 D-41），倍率由日历 + 常数包决定。

---

## 六、下一步第一件事（M4 启动）

1. `tools/bench.py` 增补"参数推导边界扫描"（B2 扩为不依赖真值库样本的规则表推导边界，含 ±0.01 邻域）——对应 M4-2。
2. 补双向对账（公式推导 vs 穷举恢复）：年休假分档边界、加班三档倍率、二倍工资月数区间——对应 M4-3。
3. 补 `tools/bench.py` `EXIT_USAGE=2` 通路断言；收尾落盘 HANDOFF-M5。

---

## 七、关键命令速查

```bash
# 环境（本机）
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=code/src          # 未 pip install -e 时需要

# 测试（双解释器）
py -X utf8 -m pytest code/tests -q
py -3.8 -X utf8 -m pytest code/tests -q
# 全绿但退出码 139 → 清缓存重跑：
find . -name __pycache__ -type d -prune -exec rm -rf {} +

# 基准（M2 起）
py -X utf8 tools/bench.py                 # 达标 exit 0 / 未达标 exit 1
py -X utf8 tools/bench.py --json          # 结构化指标（写 README 用）

# 门禁五连
py -X utf8 tools/check_no_literals.py
py -X utf8 tools/gen_rulesets.py --check
py -X utf8 tools/gen_cases.py --check
py -X utf8 tools/dessensitize_audit.py --mode tracked
py -X utf8 tools/dessensitize_audit.py --mode messages
py -X utf8 tools/dessensitize_audit.py --mode history      # 建仓后复核用

# CLI
py -X utf8 -m lcc params
py -X utf8 -m lcc doctor
py -X utf8 -m lcc calc examples/sample-case.json --modules severance   # 只跑经济补偿
py -X utf8 -m lcc calc examples/sample-case.json                       # 默认四模块 → exit 0
py -X utf8 -m lcc calc --preview examples/sample-case.json             # 预览不输出金额 → exit 1

# 生成器重生成（改了 sources/verified-params.json 或年度区间后）
py -X utf8 tools/gen_rulesets.py
py -X utf8 tools/gen_cases.py
```

---

## 八、缓议项（收尾前须闭环）

| 编号 | 事项 | 状态 |
|---|---|---|
| R-01 | 代通知金基数口径 | ✅ 已闭环（D-30） |
| R-02 | 年休假折算取整方向 | ✅ 已闭环（D-31） |
| R-03 | 不定时工作制法定节假日加班费 | ✅ 已闭环（D-41：倍率不随工时制度变化；地区例外留待逐地区参数化） |
| R-04 | 试点地区选择 | ✅ 已闭环（D-35） |
| R-06 | 技术报告是否出 docx 版 | ⬜ M5 定夺 |
