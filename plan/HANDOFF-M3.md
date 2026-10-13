# HANDOFF-M3：M2 经济补偿引擎 → M3 其余三引擎

> 交接快照（ai-tool-project-sprint 阶段 0）。**新对话续接用法**：
> `/goal 读取 "plan/HANDOFF-M3.md" 继续完成任务`（入库文件内一律写相对路径）。
> 快照日期：2026-10-13 ｜ 上一里程碑：**M2 经济补偿引擎** ｜ 下一棒：**M3 加班费/年休假/二倍工资**

---

## 一、当前进度（M2 已完成什么）

### 1.1 经济补偿引擎落地（`code/src/lcc/engine/severance.py`）

| # | 能力 | 实现要点 | 证据 |
|---|---|---|---|
| M2-1 | 口径判定 9 种情形 | `determine_formula()` → `{ground, formula, basis, reason}`；易混边界：第 40 条**未**通知 → N+1（非 2N）、第 39 条 → none（0）、第 38 条 → N | 基准 B1 **9/9 = 100%**；`test_determine_formula_nine_cases` |
| M2-2 | 工作年限取整 | 完整月数 + 余日（≥15 天计 0.5 月，D-34）→ 第 47 条取整（满 6 个月不满 1 年按 1 年、不满 6 个月按 0.5） | 5/6/11/12 月边界 + 余日 0/14/15 天全对；`service_years_for_compensation` |
| M2-3 | 三倍封顶 + 12 年上限 | 切换点 = **严格大于**（恰好等于封顶基数**不**封顶）；封顶时年限 ≤ 12 | `cap_minus_cent/cap_at/cap_plus_cent` 三档全对；137/144/146/156 月四档全对 |
| M2-4 | 最低工资下限 | 月工资 < 最低工资 → 取下限（**仅经济补偿**；代通知金不受约束） | `test_min_wage_floor_applied` |
| M2-5 | 依据条款 | 按口径挂 `LCL-46/47`（N）、`LCL-40/47`（N+1）、`LCL-48/87`（2N）、`none` 无依据 | `test_basis_ids_are_formula_specific_and_resolvable`；`test_severance_engine_basis_ids_all_resolvable` |
| M2-6 | 算例回归 100% | 真值库 406 条经引擎重算 → 逐字段 + 隐含结论对账 **0 mismatch** | `test_severance_engine_reconciles_all_truth_cases`；基准 B2 **406/406** |

**引擎输出字段**（对账/报告用）：`{formula, ground, service_years, monthly_wage_avg, last_month_wage, min_wage_applied, cap_applied, cap_base, basis_wage, years_used, years_capped, amount, steps, basis, reason}`。
其中 `basis_wage` 为**实际使用的计算基数**（封顶值 / 最低工资 / 月平均），供报告与隐含结论谓词用。

### 1.2 新增的基准与测试

| 组件 | 位置 | 说明 |
|---|---|---|
| 内置基准 | `tools/bench.py` | B1 口径判定 / B2 封顶取整边界 / B3 参数库自洽 + **阳性对照**；退出码 0 达标 / 1 未达标 |
| 引擎单测 | `code/tests/test_engine_severance.py` | 37 项：九情形、易混边界、年限/封顶/下限、依据、输入守卫、窗口取平均 |
| 真值库对账 | `code/tests/test_truth_library.py` | 新增 2 项：全量 severance 对账 + 依据可解析 |
| 基准守门 | `code/tests/test_bench.py` | 8 项：B1/B2/B3 达标 + 阳性对照 + 退出码语义 + 离线快跑 |
| CLI 端到端 | `code/tests/test_cli_exit_codes.py` | 更新：severance 出金额（exit 0）、四模块默认报 M3（exit 1）、预览不输出金额（exit 1） |

### 1.3 一处真值检查器自洽修正（D-39，**未动冻结真值**）

`benchmark/cases.py::_pred_n_plus_1_uses_last_month_wage` 原实现为「封顶时上月工资必须 > 封顶基数」，与真值自身 `expected.amount` 矛盾——上月工资**恰好等于**封顶基数的合法巧合会被误判（全量对账实测命中 1 例：`pilot-110000-2026-100`，工资序列含恰好等于封顶基数 36348.00 的月份）。改为等价式判定（从 `amount` 剥离 N 部分后余量须等于 `last_month_wage`，容差 0.10）。
- **只改检查器谓词**；`expected`/`also_expect`/`input_facts` 不变 → `tools/gen_cases.py --check` 仍 `FROZEN_TRUTH_OK`（406 条逐字节一致）。
- 改后：50 条 N+1 全部通过 + 50 条篡改对照全部被捕获（正负双向验证）。
- 决策留档：plan/06 **D-39**。

### 1.4 M2 完成判据（已实测达成）

> `cases-pilot.json` + `cases-boundary.json` 中 `severance` 模块全部对账 0 mismatch，且基准 B1 口径判定 100%。

实测：

```
$ py -X utf8 tools/bench.py
[OK]   B1 口径判定: 9/9（目标 100%）
[OK]   B2 封顶与取整边界: 406/406（目标 全通过）
[OK]   B3 参数库自洽（拦截率）: 5/5（目标 100%）
[OK]   阳性对照（已核对坐标放行）: 4/4（目标 全通过）
基准结论：全部达标
```

### 1.5 验证证据（M2 收尾实跑）

- 全量 pytest：**144 passed**（本机 3.8.8 与 3.12.10 双验，收集数一致）。
- 四道门禁：`NO_POLICY_LITERALS_OK`（11 文件 0 命中）/ `FROZEN_RULESETS_OK` / `FROZEN_TRUTH_OK` / `DESSENSITIZE_AUDIT_OK`（tracked 模式）。
- CLI 冒烟：`params` / `doctor` exit 0；`calc --modules severance`（上海 2026）**exit 0 并出金额 79029.17 元**；`calc`（默认四模块）exit 1 报 M3；`calc --preview` exit 1 且不输出金额。
- 基准全达标（见 §1.4）。

### 1.6 CI（M2 闭环）

- 提交 `af6de10`（引擎实现）推送 `origin/main` → **CI 全绿**（run `38392116791`）：三矩阵
  `ubuntu-latest/py3.12` + `windows-latest/py3.12` + `windows-latest/py3.8` 全部 ✓。
- 提交 `d781fa1`（本回写）再推 → **CI 全绿**（run `38392350209`，三矩阵同样全 ✓）。
- workflow 步骤：Repo gates（literals / frozen rulesets / **frozen truth** / dessensitize）、
  **Benchmarks (B1/B2/B3)**、Run tests、CLI smoke（新增 `calc --modules severance` 冒烟）各步均 ✓。
- 说明：CI 日志仍有 Node.js 20 弃用提示与 ubuntu 镜像迁移预告（actions 版本层面，非本项目失败）。
- push 事件数 = run 数：2 次 push = 2 个 run，对账成立（`git rev-list --count` 数的是提交数，勿混用）。

---

## 二、M3 待办（下一棒做什么）

| # | 任务 | 关键点 |
|---|---|---|
| M3-1 | 加班费引擎 `engine/overtime.py` | 工时制度区分（standard/comprehensive/irregular）+ 三档倍率 + **日历四类联动**（`ruleset.holiday_day_type`，含 M1 新增 `rest_days` → 200%）；基数 = 劳动者月工资（D-33，不低于最低工资）÷（`monthly_pay_days` × `overtime.standard_daily_hours`） |
| M3-2 | 年休假引擎 `engine/annual_leave.py` | 分档（`entitlement_tiers`）+ 当年度折算（`days_per_year`）+ 冲抵（`unused_multiple` 含已付 `already_paid_portion`）；**取整方向 R-02 已闭环**（D-31：向下取整，作用于扣除已休后的应休未休天数） |
| M3-3 | 二倍工资引擎 `engine/double_wage.py` | 起算（满 `start_after_months` 个月次日）+ 上限（`max_months`）+ 差额倍数（`difference_multiple`） |
| M3-4 | 三引擎挂依据 + 对账 | 结果挂条款依据；**每实现一块就跑 `benchmark.cases.compare`** 对全量真值库（406 条含 overtime/annual_leave/double_wage 模块） |
| M3-5 | 基准扩展 | `tools/bench.py` 的 B2 覆盖面扩到三模块（当前只跑 severance）；指标写 README 评测表 |

**M3 完成判据（建议）**：真值库 406 条中 `overtime`/`annual_leave`/`double_wage` 三模块全部对账 0 mismatch；`tools/bench.py` 全达标。

> **实现顺序建议**：先 overtime（日历联动已在 M1 就位、四类判定单点），再 annual_leave（取整口径已定稿），最后 double_wage（纯日历算术，与 severance 的 `_add_months` 同构）。每完成一个就跑一次全量对账。

---

## 三、既定口径清单（动了会打挂基准/测试的约定）

1. **真值语义**：`expected` 主期望 + `also_expect` 隐含结论；对账按"全部非 pass 字段集"；语义**单一实现源** `lcc/benchmark/cases.py`。
2. **不许改真值凑引擎**：发现口径错误改引擎 + 加测试。**但检查器谓词自身不自洽**时，可改谓词（不动冻结产物）——M2 的 D-39 即此例；判据是 `gen_cases.py --check` 仍 `FROZEN_TRUTH_OK`。
3. **Decimal 口径**：JSON `parse_float=Decimal`；金额量化两位 `ROUND_HALF_UP`；天数记录精度 6 位。已定稿取整方向：年休假应休未休天数**向下取整**（R-02，D-31）；年限余日 ≥15 天计 0.5 月（D-34）。
4. **status 门控单点**：只有 `gate.effective_ruleset()` 产出可计算规则集；引擎签名只接受 `EffectiveRuleset`。
5. **坐标精确匹配**：`load_ruleset` 不做模糊/回退；跨坐标必须报错。
6. **零政策字面量**：法定数值只来自数据包；`tools/check_no_literals.py` 扫描 engine/benchmark/gui/pipeline（含 docstring/注释）。**新增引擎代码前先看该脚本的 `BANNED_TOKENS`**（当前禁用：21.75 / 365 / 150·200·300 及其百分号形态 / 1.5·2.0·3.0）。
7. **退出码**：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误；**`--preview` 命中门控 → exit 1 且不进入引擎**（M2 修正：预览模式不跑引擎）。
8. **测试全离线**：零网络、零 API、无外部 mock。
9. **冻结产物纪律**：`data/rules/*` 与 `data/truth/*` 均为生成器产出，**禁手改**；文本 `write_bytes` + `\n`。
10. **引擎层不得 import CLI/GUI**；核心层零第三方依赖。
11. **日历唯一来源**：日期类型判定只在 `ruleset.holiday_day_type()`（四类：`statutory_holiday`/`rest_day`/`adjusted_workday`/`workday`），引擎不得自建日历逻辑。
12. **引擎输出含 `basis_wage`**：M2 起经济补偿输出含"实际计算基数"字段，隐含结论谓词优先用它。

### 三.1 月工资口径（D-32）

`monthly_wages` 单序列同时服务经济补偿与年休假，约定为**「应得工资、剔除加班工资」**：第 47 条口径（应得工资）∩ 实施办法第十一条口径（剔除加班工资）。

### 三.2 加班基数口径（D-33，M3 用）

M1 真值语义取**劳动者月工资**（12 个月平均，不低于当地最低工资）。规则包级 `overtime_base_caliber` 与不定时工作制口径差异并入 **R-03**（M3 前定）。

### 三.3 日历三字段（M3 必读）

`holiday_calendar` 现为三字段（M1 新增 `rest_days`）：

| 字段 | 日期类型 | 未补休倍率 |
|---|---|---|
| `days` | `statutory_holiday` | 300% |
| `rest_days` | `rest_day`（调休/连休中的非法定日） | 200% |
| `adjusted_workdays` | `adjusted_workday` | 200% |
| （其余） | `workday` | 150% |

> 背景：放假安排里「放假调休 N 天」中的非法定节假日仍是**休息日**。若只登记 `days`+`adjusted_workdays`，这些日期会退化成工作日口径 → 系统性少算。已在 plan/04 §4.3 与守门测试中固化。

### 三.4 年休假取整（D-31，M3 必读）

取整方向 = **向下取整（不足 1 整天不计）**，作用于**「应休未休天数」这一最终量**（`floor(折算应休天数 − 当年度已安排天数)`），下限截 0；折算应休天数本身保留原值供报告展示。真值实现见 `benchmark/cases.py::annual_leave_expected`，引擎必须与之逐字段一致。

---

## 四、本机环境坑（全部实测）

- **本机有 3.8.8 与 3.12.10**（`py -0p`）：3.8 上 `pytest` 解析到 **8.3.5**；**别把"本机 3.12 能跑"当 3.8 证据**。M2 已双验 144 passed。
- **`py -X utf8` 是本机习惯、也是 CI 盲区**：入口 `_ensure_utf8_stdio()` 是必需品。
- **pyc 偶发损坏 / 退出期 segfault**：全程 `PYTHONDONTWRITEBYTECODE=1`；若见 pytest 全绿但退出码 139，先 `find . -name __pycache__ -prune -exec rm -rf {} +` 再跑。
- **Git Bash `/tmp` ≠ Python 的 `/tmp`**：给 CLI 传文件路径时用**仓库内相对路径**（如 `.scratch/x.json`），不要用 `/tmp`。
- **`--modules` 是 `nargs="+"`**：位置参数 `input` 必须写在 `--modules` **之前**（`lcc calc <input> --modules severance`），否则 argparse 把文件路径吞进 `--modules`。
- **pip 代理污染**：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- **venv 通道**：Git Bash 下用 `./.venv/Scripts/python.exe` 相对形式；`py` 启动器会绕过 venv。
- **数据目录显式传入不参与回退**（给错即报错）——刻意的，防假绿。

---

## 五、DoD 逐项核对（M2）

| # | DoD | 状态 | 证据 |
|---|---|---|---|
| M2-1 | 口径判定 9 种情形全部实现 + 基准 B1 100% | ✅ | B1 9/9；`test_determine_formula_nine_cases` |
| M2-2 | 年限取整（5/6/11/12 个月边界）实现 + 边界基准通过 | ✅ | `test_service_years_rounding`；B2 406/406 |
| M2-3 | 三倍封顶（恰好/±0.01）+ 12 年上限（11.5/12/12.5/13）实现 + 边界基准通过 | ✅ | `test_cap_switch_point_is_strict_greater`、`test_cap_twelve_year_limit` |
| M2-4 | 最低工资下限生效 | ✅ | `test_min_wage_floor_applied` |
| M2-5 | 结果挂 `LCL-47` 等依据；代通知金口径核对后定稿 | ✅ | 挂 `LCL-46/47/40/48/87`；代通知金 D-30（上月工资、不受封顶/下限） |
| M2-6 | 算例回归 100%（合成档案真值对账） | ✅ | `test_severance_engine_reconciles_all_truth_cases`（406/406） |

**偏差说明**：M2 期间发现并修正真值**检查器**谓词一处不自洽（D-39，未动冻结真值，`FROZEN_TRUTH_OK` 保持）。M2 只实现 severance；其余三引擎按计划留 M3。

---

## 六、下一步第一件事（M3 启动）

1. 实现 `engine/overtime.py`（日历四类联动 + 工时制度），跑全量对账（`benchmark.cases.compare` 的 `overtime` 模块）。
2. 依次实现 `annual_leave.py`、`double_wage.py`，每块实现后立刻跑全量对账。
3. M3 收尾把 `tools/bench.py` 的 B2 覆盖面扩到三模块，指标写进 README 评测表；落盘 HANDOFF-M4。

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
py -X utf8 -m lcc calc examples/sample-case.json --modules severance   # exit 0，出金额
py -X utf8 -m lcc calc examples/sample-case.json                       # 默认四模块 → exit 1（待 M3）
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
| R-03 | 不定时工作制法定节假日加班费 | ⬜ **M3 前**；M1 真值语义暂按劳动者月工资（D-33） |
| R-04 | 试点地区选择 | ✅ 已闭环（D-35） |
| R-06 | 技术报告是否出 docx 版 | ⬜ M5 定夺 |
