# HANDOFF-M2：M1 数据先行 → M2 经济补偿引擎

> 交接快照（ai-tool-project-sprint 阶段 0）。**新对话续接用法**：
> `/goal 读取 "plan/HANDOFF-M2.md" 继续完成任务`（入库文件内一律写相对路径）。
> 快照日期：2026-10-13 ｜ 上一里程碑：**M1 数据先行** ｜ 下一棒：**M2 经济补偿引擎**

---

## 一、当前进度（M1 已完成什么）

### 1.1 数据全部核对并置 verified

| 数据 | 条目 | 状态 | 关键证据 |
|---|---|---|---|
| `data/constants/statutory-constants.json` | 21 条 | ✅ 全 verified | 逐条挂条号 + 官方 URL + 原文摘录；新增 3 条（日工时 8、赔偿金倍数 2、二倍工资差额倍数 1） |
| `data/law/clauses.json` | 17 条 | ✅ 全 verified | 新增 `LL-36`（日工时依据）；要点与官方原文一致 |
| `data/regions/regions.json` | 4 地区 | 京沪 verified / 粤苏 pending | 口径字段逐地区登记 |
| `data/rules/*` | 8 份 | **4 verified**（京沪×2025/2026）/ 4 pending（粤苏） | 由生成器从 `data/sources/verified-params.json` 合并 |
| `data/sources/verified-params.json` | 4 坐标 | ✅ verified | **人工核对清单**：数值 + 机关 + 年度 + 口径 + URL + 抓取日期 + 派生说明 |
| `data/truth/cases-pilot.json` | 320 条 | ✅ | 覆盖矩阵：9 口径 × 年限 5/6/11/12 月与 11.5/12/12.5/13 年 × 封顶三档 × 工时制度 × 年休假分档 × 二倍工资 |
| `data/truth/cases-boundary.json` | 86 条 | ✅ | 封顶恰好 ±0.01、年限余日 0/14/15 天、分档 1/10/20 年、二倍工资起止与 11 月上限 |

**试点地区（R-04 闭环）**：北京市(110000) + 上海市(310000) × 2025/2026 = 4 坐标全 verified。

### 1.2 新增/改造的代码

| 组件 | 位置 | 说明 |
|---|---|---|
| 真值语义单一实现源 | `code/src/lcc/benchmark/cases.py` | 四模块真值 + `also_expect` 谓词表 `IMPLICATIONS`；**不许改真值凑引擎** |
| 自研 RNG | `code/src/lcc/benchmark/rng.py` | SplitMix64（无 stdlib `random`），已对齐参考序列 |
| 合成档案生成器 | `tools/gen_cases.py` | 固定种子、确定性落盘、`--check` 位级一致 |
| 日历四分类 | `params.py` / `gate.py` | 新增 `rest_days` 与 `holiday_day_type()`（**新增 `rest_days` 字段**，见 §三.3） |
| 常数取数 | `gate.py` | 新增 `standard_daily_hours` / `compensation_multiple` / `double_wage_difference_multiple` / `overtime_standard_daily_hours` |
| 真值库守门 | `code/tests/test_truth_library.py` | 13 项：位级一致、独立重算对账、阳性对照、覆盖矩阵、封顶切换点 |

### 1.3 M1 完成判据（已实测达成）

> 至少一个 `(地区, 年度)` 坐标下全部条目 `verified`，且 `lcc calc` 能穿过门控进入引擎
> （此时会报 M2 未实现 —— 这本身就是门控已放通的证据）。

实测（真值库真实记录直接喂 CLI）：

```
$ lcc calc <110000/2025 真值记录>      → exit 1，stderr「经济补偿引擎将在 M2 实现」
$ lcc calc <440000/2026 同结构输入>    → exit 2，stderr「门控拦截：3 个条目尚未核对」
```

已锁进 `code/tests/test_cli_exit_codes.py::test_calc_real_truth_record_passes_gate`。

### 1.4 验证证据（M1 收尾实跑）

- 全量 pytest：**96 passed**（本机 3.8.8 与 3.12.10 双验，收集数一致）。
- 四道门禁：`NO_POLICY_LITERALS_OK`（11 文件 0 命中）/ `FROZEN_RULESETS_OK` / `FROZEN_TRUTH_OK` / `DESSENSITIZE_AUDIT_OK`（tracked + messages + history 三模式全过）。
- CLI 冒烟：`params` / `doctor` exit 0；已核对坐标 exit 1（进引擎）；未核对坐标 exit 2（门控）。
- 真值库：406 条全部可由 `cases.evaluate` 独立重算对上（`test_stored_truth_recomputes_from_single_source`）。

### 1.5 建仓与 CI（**M0-12 闭环**）

- 仓库已建：`yuluo554/labor-compliance-calculator`（public）；远端为 SSH 形态（`git@github.com:...`，不受 OAuth `workflow` scope 限制）。
- 建仓方式按 D-24：`gh repo create ... --source . --remote origin`（**不带 `--push`**）→ `git remote set-url origin git@...` → `git push -u origin main` 一次成。
- **CI 首跑全绿**（run `38386506901`）：三矩阵 `ubuntu-latest/py3.12` + `windows-latest/py3.12` + `windows-latest/py3.8` 全部 ✓；workflow 内「Repo gates（literals / frozen rulesets / dessensitize）」「Run tests」「CLI smoke」各步均 ✓。第二次 push 亦全绿（run `38387380042`）。
- **push 事件数 = run 数**：本地既有 8 个提交在**首次 push** 一次性上传 → 触发 1 个 workflow run（GitHub 按 **push 事件**计，不按提交数计）；M1 回写 push 触发第 2 run → 2 push = 2 run，对账成立。（`git rev-list --count` 数的是提交数，不是 push 数，勿混用。）
- 说明：CI 日志有 Node.js 20 弃用提示与 ubuntu 镜像迁移预告（actions 版本层面，非本项目失败）；后续升级 actions 版本时可一并处理。
- 全历史脱敏：`--mode messages` 与 `--mode history` 均 `DESSENSITIZE_AUDIT_OK`（提交信息与全历史无敏感命中）。

---

## 二、M2 待办（下一棒做什么）

| # | 任务 | 关键点 |
|---|---|---|
| M2-1 | 口径判定 9 种情形实现 + 基准 B1 通过率 100% | 映射表见 `engine/severance.py::FORMULA_BY_GROUND`；易混边界：第 40 条未提前通知 → N+1（非 2N）、第 39 条 → 0、第 38 条 → N |
| M2-2 | 年限取整（5/6/11/12 个月边界） | 口径已定：完整月数 + 余日（≥15 天计 0.5 月）→ 第 47 条取整；**真值实现见 `benchmark/cases.py::service_years_for_compensation`，引擎必须与之逐字段一致** |
| M2-3 | 三倍封顶（恰好/±0.01）+ 12 年上限 | 切换点语义 = **严格大于**（恰好等于封顶基数**不**封顶）；封顶时年限 ≤ 12 |
| M2-4 | 最低工资下限生效 | 月工资 < 最低工资 → 取最低工资（**仅经济补偿**） |
| M2-5 | 结果挂 `LCL-46/47/48/87` 等依据；代通知金口径 | **R-01 已闭环**：代通知金 = 上一个月工资（非平均），不受封顶/下限约束（plan/06 D-30） |
| M2-6 | 算例回归 100%（真值库对账） | 用 `benchmark.cases.compare(case, spec, actual, ruleset)`；`actual` = 引擎输出 `{module: {字段: 值}}` |

**M2 完成判据（建议）**：`cases-pilot.json` + `cases-boundary.json` 中 `severance` 模块全部对账 0 mismatch，且基准 B1 口径判定 100%。

---

## 三、既定口径清单（动了会打挂基准/测试的约定）

1. **真值语义**：`expected` 主期望 + `also_expect` 隐含结论；对账按"全部非 pass 字段集"；语义**单一实现源** `lcc/benchmark/cases.py`。
2. **不许改真值凑引擎**：发现口径错误改引擎 + 加测试。
3. **Decimal 口径**：JSON `parse_float=Decimal`；金额量化两位 `ROUND_HALF_UP`；天数记录精度 6 位。**已定稿的取整方向**：年休假应休未休天数**向下取整**（R-02，D-31）；年限余日 ≥15 天计 0.5 月（D-34）。
4. **status 门控单点**：只有 `gate.effective_ruleset()` 产出可计算规则集；引擎签名只接受 `EffectiveRuleset`。
5. **坐标精确匹配**：`load_ruleset` 不做模糊/回退；跨坐标必须报错。
6. **零政策字面量**：法定数值只来自数据包；`tools/check_no_literals.py` 扫描 engine/benchmark/gui/pipeline（含 docstring/注释）。**新增引擎代码前先看该脚本的 `BANNED_TOKENS`**。
7. **退出码**：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误。
8. **测试全离线**：零网络、零 API、无外部 mock。
9. **冻结产物纪律**：`data/rules/*` 与 `data/truth/*` 均为生成器产出，**禁手改**；文本 `write_bytes` + `\n`。
10. **引擎层不得 import CLI/GUI**；核心层零第三方依赖。
11. **日历唯一来源**：日期类型判定只在 `ruleset.holiday_day_type()`（四类：`statutory_holiday`/`rest_day`/`adjusted_workday`/`workday`），引擎不得自建日历逻辑。

### 三.1 月工资口径（D-32，M2 必读）

`monthly_wages` 单序列同时服务经济补偿与年休假，约定为**「应得工资、剔除加班工资」**：
- 第 47 条口径 = 应得工资（含奖金/津贴/补贴等货币性收入）；
- 实施办法第十一条口径 = 剔除加班工资后的月平均工资；
- 取交集 → 一个字段满足两处。

### 三.2 加班基数口径（D-33，M3 用）

M1 真值语义取**劳动者月工资**（12 个月平均，不低于当地最低工资）。规则包级 `overtime_base_caliber` 与不定时工作制口径差异并入 **R-03**（M3 前定）。

### 三.3 日历三字段（M3 必读）

`holiday_calendar` 现为三字段（**M1 新增 `rest_days`**）：

| 字段 | 日期类型 | 未补休倍率 |
|---|---|---|
| `days` | `statutory_holiday` | 300% |
| `rest_days` | `rest_day`（调休/连休中的非法定日） | 200% |
| `adjusted_workdays` | `adjusted_workday` | 200% |
| （其余） | `workday` | 150% |

> 背景：放假安排里「放假调休 N 天」中的非法定节假日仍是**休息日**。若只登记 `days`+`adjusted_workdays`，这些日期会退化成工作日口径 → 系统性少算。已在 plan/04 §4.3 与守门测试中固化。

---

## 四、本机环境坑（全部实测）

- **本机有 3.8.8 与 3.12.10**（`py -0p`）：3.8 上 `pytest` 解析到 **8.3.5**；**别把"本机 3.12 能跑"当 3.8 证据**。
- **`py -X utf8` 是本机习惯、也是 CI 盲区**：入口 `_ensure_utf8_stdio()` 是必需品。
- **pyc 偶发损坏 / 退出期 segfault**：全程 `PYTHONDONTWRITEBYTECODE=1`；若见 pytest 全绿但退出码 139，先 `find . -name __pycache__ -prune -exec rm -rf {} +` 再跑（本机已复现一次，清缓存后三连稳定 96 passed）。
- **Git Bash `/tmp` ≠ Python 的 `/tmp`**：给 CLI 传文件路径时用**仓库内相对路径**（如 `.scratch/x.json`），不要用 `/tmp`（Python 会解析成 `C:/Users/.../Temp`）。
- **pip 代理污染**：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- **venv 通道**：Git Bash 下用 `./.venv/Scripts/python.exe` 相对形式；`py` 启动器会绕过 venv。
- **数据目录显式传入不参与回退**（给错即报错）——刻意的，防假绿。

---

## 五、DoD 逐项核对（M1）

| # | DoD | 状态 | 证据 |
|---|---|---|---|
| M1-1 | 选定试点地区（≥2 省 × ≥2 年度）并核对社平/最低工资，挂来源 | ✅ | 京沪×2025/2026；`data/sources/verified-params.json` |
| M1-2 | 法定常数包逐条核对 → verified + source | ✅ | 21 条全 verified |
| M1-3 | 条款库覆盖 FR-2~FR-5 全部引用条款 | ✅ | 17 条全 verified |
| M1-4 | 法定节假日日历按年度入库（含调休） | ✅ | days/rest_days/adjusted_workdays 三分类，挂国办发明电来源 |
| M1-5 | `tools/gen_cases.py` + 真值库（固定种子，逐字节一致） | ✅ | 406 条；`FROZEN_TRUTH_OK` |
| M1-6 | `data/README.md` 台账逐条登记 sha256 + 来源 + 核对结论 | ✅ | §三 分 verified/pending 两表 |
| M1-7 | 「再生成逐字节一致」守门测试通过 | ✅ | `test_truth_library.py::test_truth_library_regenerates_byte_identical` + rules 既有守门 |

**偏差说明**：粤苏 4 份规则包保持 `pending`（未核对）——这是设计行为，证明"未核对即拒绝计算"机制有效；M1+ 或 M2 期间按需核对。

---

## 六、下一步第一件事（M2 启动前）

1. **建仓并接 CI**：✅ **已完成**（见 §1.5）——仓库已建、CI 首跑三矩阵全绿、全历史脱敏通过。
2. 然后进入 M2：先实现 `engine/severance.py`，每实现一块就跑 `cases-pilot/boundary` 的 `severance` 对账（`benchmark.cases.compare`）。
3. M2 收尾跑基准 B1（口径判定 100%）并把指标写进 README 评测表。

---

## 七、关键命令速查

```bash
# 环境（本机）
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=code/src          # 未 pip install -e 时需要

# 测试
py -X utf8 -m pytest code/tests -q
# 全绿但退出码 139 → 清缓存重跑：
find . -name __pycache__ -type d -prune -exec rm -rf {} +

# 门禁四连
py -X utf8 tools/check_no_literals.py
py -X utf8 tools/gen_rulesets.py --check
py -X utf8 tools/gen_cases.py --check
py -X utf8 tools/dessensitize_audit.py --mode tracked
py -X utf8 tools/dessensitize_audit.py --mode messages
py -X utf8 tools/dessensitize_audit.py --mode history      # 建仓后复核用

# CLI
py -X utf8 -m lcc params
py -X utf8 -m lcc doctor
#   examples/sample-case.json 用 310000/2026（M1 已 verified）→ 门控放行进引擎 → exit 1（待 M2）
py -X utf8 -m lcc calc examples/sample-case.json
#   要看门控拦截（exit 2）的演示：把输入 region_code 改为 440000（广东仍 pending）
py -X utf8 -m lcc calc --preview examples/sample-case.json  # 预览参数元信息（不输出金额）

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
| R-03 | 不定时工作制法定节假日加班费 | ⬜ M3 前；M1 真值语义暂按劳动者月工资（D-33） |
| R-04 | 试点地区选择 | ✅ 已闭环（D-35） |
| R-06 | 技术报告是否出 docx 版 | ⬜ M5 定夺 |
