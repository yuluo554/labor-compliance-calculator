# HANDOFF-M5：M4 基准完善 → M5 桌面交付

> 交接快照（ai-tool-project-sprint 阶段 0）。**新对话续接用法**：
> `/goal 读取 "plan/HANDOFF-M5.md" 继续完成任务`（入库文件内一律写相对路径）。
> 快照日期：2026-10-13 ｜ 上一里程碑：**M4 基准完善** ｜ 下一棒：**M5 桌面交付**

---

## 一、当前进度（M4 已完成什么）

### 1.1 基准由三类扩为五类（`tools/bench.py`）

| # | 基准 | 实现要点 | 证据 |
|---|---|---|---|
| B1 | 口径判定 | 解除情形 → N/N+1/2N/none 枚举（含易混边界）+ 覆盖模型全部 ground | **9/9** |
| B2 | 边界与全模块对账 | 真值库 406 条经**四引擎**重算，逐字段 + 隐含结论对账 | **406/406** |
| B3 | 参数库自洽 | 不存在坐标 / 年度回退 / 跨坐标混用 / pending 条目 → 拦截 | **5/5** |
| **B4** | **参数推导边界扫描（M4 新增）** | **不依赖真值库样本**：切换端点全部由规则表/常数包推出，±0.01 邻域断言 | **96/96** |
| **B5** | **双向对账（M4 新增）** | 公式推导端点 vs 穷举扫描恢复切换点，两条独立路径互验 | **40/40** |
| — | 阳性对照 | 已核对坐标必须放行（防"拦截率 100%"是"什么都拦"空验） | **4/4** |

**B4 覆盖面**（每个已核对坐标 × 8 组）：
封顶切换点 ±0.01（严格大于：恰好等于不封顶）、最低工资下限 ±0.01（严格小于）、
年限取整阈值（`full_year_threshold_months` 个月边界）、余日 14/15 天、
12 年上限（封顶时年限 ≤ `cap_years`）、加班三档倍率（日历四类 → 常数包三档）、
年休假分档下界闭合/上界开 + 累计不满最低档 → 0 天（D-42）、二倍工资起算日 + 区间上限。

**B5 覆盖面**（每个已核对坐标 × 6 组）：封顶切换点、年限取整切换点、12 年上限、
年休假分档边界、加班倍率映射、二倍工资起算日与区间（穷举覆盖 `0..max_months`）。

**B4 vs B2 分工**：B2 是"真值库记录重算对账"（**样本驱动**）；B4 是"**规则驱动**"——
不依赖真值库是否恰好覆盖某端点。**B4 vs B5 分工**：B4 验"端点应当在哪"，B5 验"引擎实际行为在端点处与参数语义吻合"。

### 1.2 `tools/bench.py` 退出码三语义齐备（M4-4）

- 新增 `--only <NAME>`（`B1`/`B2`/`B3`/`B4`/`B5`/`positive`）：未知名 → **exit 2（`EXIT_USAGE`）**。
- 三退出码 0/1/2 全部锁进 `code/tests/test_bench.py`：
  `test_bench_exit_codes_are_0_1_2`（常量）+ `test_bench_exit_code_zero_when_all_pass`（0）+
  `test_bench_reports_below_target_as_exit_one`（1）+ `test_bench_unknown_only_is_exit_usage`（2）。

### 1.3 非空验（防"只跑通抓不住漂移"）

`code/tests/test_bench.py` 内**阳性对照**注入语义漂移，断言基准**必须报失败**：

- `test_b4_detects_cap_switch_drift`：封顶比较 `>`→`>=` → B4 必须 FAIL；
- `test_b5_detects_year_rounding_drift`：年限阈值 `>=`→`>` → B5 必须 FAIL。

另加 `test_b4_does_not_read_truth_library` / `test_b5_does_not_read_truth_library`：
临时清空真值库后 B4/B5 仍须全通过（证明二者确为规则驱动）。

**实测**：对引擎源码注入 4 类漂移（封顶 `>=`、年限阈值 `>`、年休假分档下界 `>`、
二倍工资首月 −1），B4 与 B5 **全部捕获**（每条至少一侧 FAIL）。

### 1.4 M4 完成判据（已实测达成）

> B4 边界扫描覆盖"参数推导边界"（不靠真值库样本）且 0 失败；双向对账一致；
> `tools/bench.py` 三退出码语义均有测试。

实测：

```
$ py -X utf8 tools/bench.py
[OK]   B1 口径判定: 9/9（目标 100%）
[OK]   B2 边界与全模块对账: 406/406（目标 全通过）
[OK]   B3 参数库自洽（拦截率）: 5/5（目标 100%）
[OK]   B4 参数推导边界扫描: 96/96（目标 全通过）
[OK]   B5 双向对账（公式推导 vs 穷举恢复）: 40/40（目标 全通过）
[OK]   阳性对照（已核对坐标放行）: 4/4（目标 全通过）
基准结论：全部达标
```

### 1.5 验证证据（M4 收尾实跑）

- 全量 pytest：**178 passed**（本机 3.8.8 与 3.12.10 双验，收集数一致）。
- 五道门禁：`NO_POLICY_LITERALS_OK`（11 文件 0 命中）/ `FROZEN_RULESETS_OK` / `FROZEN_TRUTH_OK` / `DESSENSITIZE_AUDIT_OK`（tracked + messages）。
- CLI 冒烟：`params` / `doctor` exit 0；`calc --modules severance` exit 0；`calc`（默认四模块）exit 0；`calc --preview` exit 1 且不输出金额。
- 基准全达标（见 §1.4）；`--only B4` exit 0；`--only NOPE` exit 2。

### 1.6 文档回写

- README 状态行 → **M4 完成**；评测表扩为 B1~B5 + 阳性对照（M4 实测），加"B4/B5 非空验"说明。
- plan/05 §二 → 基准由三类扩为五类，§2.2 重写为 B4/B5；M4 DoD 四项打 ✅。
- plan/00 里程碑表 M4 → ✅；文档索引补 `HANDOFF-M5`。
- plan/06 追加 **D-43**（M4 闭环决策）。
- `.github/workflows/ci.yml` 的 Benchmarks 步骤名 → `(B1 / B2 / B3 / B4 / B5)`。

### 1.7 CI

- M4 提交推送 `origin/main` → **CI 全绿**（run 见 §一.7 回写行）：三矩阵
  `ubuntu-latest/py3.12` + `windows-latest/py3.12` + `windows-latest/py3.8` 全部 ✓。

---

## 二、M5 待办（下一棒做什么）

| # | 任务 | 关键点 |
|---|---|---|
| M5-1 | `lcc.pipeline` 编排上收，CLI 与 GUI 共用同一编排（CLI 行为迁移前后一致） | pipeline 已是唯一编排源（D-13）；M5 补 GUI 复用与行为一致性守门 |
| M5-2 | PySide6 多页签（四类计算 + 参数库 + 报告），GUI 层零判定逻辑（AST 守门） | 现 `gui/app.py` 为占位（报 M5 里程碑）；需实装 |
| M5-3 | 报告导出 Markdown + XLSX（含免责声明 + 参数来源块） | `report/` 现为空占位；XLSX 走 optional extra |
| M5-4 | offscreen 冒烟 + 演示素材（PNG + GIF）入 `docs/demo/` | Qt offscreen 平台；素材须脱敏 |
| M5-5 | PyInstaller onedir 双 exe；中立目录 + `env -i` CLI 五连通过 | spec datas 白名单由 `packaging.build_datas()` 单一源产生（D-19） |
| M5-6 | 技术报告 `docs/技术报告.md` 入仓 | R-06 定夺是否出 docx 版 |

> **M5 完成判据（建议）**：GUI 四页签可跑且零判定逻辑（AST 守门）；报告导出含免责声明与参数来源；
> 双 exe 在中立目录 + `env -i` 下 CLI 五连通过；技术报告入仓。

---

## 三、既定口径清单（动了会打挂基准/测试的约定）

1. **真值语义**：`expected` 主期望 + `also_expect` 隐含结论；对账按"全部非 pass 字段集"；语义**单一实现源** `lcc/benchmark/cases.py`。
2. **不许改真值凑引擎**：发现口径错误改引擎 + 加测试。**但检查器谓词自身不自洽**时可改谓词（不动冻结产物）——D-39；**真值语义本身口径错误**须**引擎与真值同源修正**——D-42。判据均为 `gen_cases.py --check` 仍 `FROZEN_TRUTH_OK`。
3. **Decimal 口径**：JSON `parse_float=Decimal`；金额量化两位 `ROUND_HALF_UP`；天数记录精度 6 位。年休假应休未休天数**向下取整**（D-31）；年限余日 ≥15 天计 0.5 月（D-34）。
4. **status 门控单点**：只有 `gate.effective_ruleset()` 产出可计算规则集；引擎签名只接受 `EffectiveRuleset`。
5. **坐标精确匹配**：`load_ruleset` 不做模糊/回退；跨坐标必须报错。
6. **零政策字面量**：法定数值只来自数据包；`tools/check_no_literals.py` 扫描 engine/benchmark/gui/pipeline（含 docstring/注释）。**新增引擎/基准代码前先看 `BANNED_TOKENS`**（当前禁用：21.75 / 365 / 150·200·300 及其百分号形态 / 1.5·2.0·3.0）。**注意**：docstring 写"150%/200%/300%"会命中。
7. **退出码**：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误；`--preview` 命中门控 → exit 1 且不进入引擎。`tools/bench.py` 亦遵此三语义（0 达标 / 1 未达标 / 2 用法错误）。
8. **测试全离线**：零网络、零 API、无外部 mock。
9. **冻结产物纪律**：`data/rules/*` 与 `data/truth/*` 均为生成器产出，**禁手改**；文本 `write_bytes` + `\n`。
10. **引擎层不得 import CLI/GUI**；核心层零第三方依赖。
11. **日历唯一来源**：日期类型判定只在 `ruleset.holiday_day_type()`（四类），引擎不得自建日历逻辑。
12. **引擎输出含 `amount`**：四引擎输出均含 `amount` 字段，CLI/报告据此判定"有无金额"。
13. **基准分层（M4 起）**：B2 样本驱动（真值库重算）；**B4/B5 规则驱动**（不读真值库，端点由参数包推出）；新增基准须进 `_BENCHMARK_KEYS` 以支持 `--only`。

### 三.1 月工资口径（D-32）

`monthly_wages` 单序列同时服务经济补偿/年休假/加班费/二倍工资，约定为**「应得工资、剔除加班工资」**。

### 三.2 加班基数与工时制度（D-33 / D-41）

- 加班基数 = 劳动者月工资（12 个月平均，不低于最低工资），**地区无关**。
- 倍率**一律由日历日期类型 + 常数包**决定，**不随 `work_system` 变化**（D-41）；`work_system` 为记录性字段。

### 三.3 日历三字段

`holiday_calendar` 三字段：`days`（法定节假日，最高档）/ `rest_days`（调休休息日，次档）/ `adjusted_workdays`（调休上班日，次档）；其余为 `workday`（最低档）。缺 `rest_days` 会系统性少算（D-37）。

### 三.4 年休假取整（D-31）

取整方向 = **向下取整**，作用于**「应休未休天数」最终量**（`floor(折算应休天数 − 当年度已安排天数)`），下限截 0；折算应休天数本身保留原值。**累计不满 1 年 → 应休 0 天**（D-42）。

### 三.5 二倍工资区间（plan/04 §6）

起算 = 用工满 `start_after_months` 个月的**次日**（月末夹取）；硬性截止 = 用工满 `start_after_months + max_months` 个月之日；区间月数 = `_months_and_remainder(start, end)[0] + 1`（首尾含当月）；`end < start` → 0 个月。

---

## 四、本机环境坑（全部实测）

- **本机有 3.8.8 与 3.12.10**（`py -0p`）：3.8 上 `pytest` 解析到 **8.3.5**；**别把"本机 3.12 能跑"当 3.8 证据**。M4 已双验 178 passed。
- **`py -X utf8` 是本机习惯、也是 CI 盲区**：入口 `_ensure_utf8_stdio()` 是必需品。
- **pyc 偶发损坏 / 退出期 segfault**：全程 `PYTHONDONTWRITEBYTECODE=1`；若见 pytest 全绿但退出码 139，先 `find . -name __pycache__ -prune -exec rm -rf {} +` 再跑。
- **Git Bash `/tmp` ≠ Python 的 `/tmp`**：给 CLI 传文件路径时用**仓库内相对路径**（如 `.scratch/x.json`），不要用 `/tmp`。
- **`--modules` 是 `nargs="+"`**：位置参数 `input` 必须写在 `--modules` **之前**（`lcc calc <input> --modules severance`）。
- **pip 代理污染**：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- **venv 通道**：Git Bash 下用 `./.venv/Scripts/python.exe` 相对形式；`py` 启动器会绕过 venv。
- **数据目录显式传入不参与回退**（给错即报错）——刻意的，防假绿。
- **Windows 上别用 Python `open(...,"w")` 改源码做实验**：会把 `\n` 翻成 `\r\n`，触发 LF 门禁（M4 实测踩坑；实验后 `git checkout` 复原）。做变异实验请用临时副本或内存 monkeypatch。

---

## 五、DoD 逐项核对（M4）

| # | DoD | 状态 | 证据 |
|---|---|---|---|
| M4-1 | B1/B2/B3 三类基准全量跑通，指标进 README | ✅ | B1 9/9、B2 406/406、B3 5/5；README 评测表 M4 实测 |
| M4-2 | 边界自洽扫描（规则表推导 + ±0.01 邻域）全通过 | ✅ | B4 **96/96**（不依赖真值库样本）；`test_b4_*` 4 项 |
| M4-3 | 双向对账（公式推导 vs 穷举恢复）一致 | ✅ | B5 **40/40**；`test_b5_*` 4 项（含漂移捕获阳性对照） |
| M4-4 | `tools/bench.py` 退出码 0/1/2 语义锁进测试 | ✅ | `--only` 未知名 → exit 2；`test_bench_exit_codes_are_0_1_2` / `test_bench_unknown_only_is_exit_usage` |

**偏差说明**：B4/B5 为 M4 新增基准（原三类扩为五类）；退出码 2 通路通过新增 `--only` 参数变为真实可达（此前 `EXIT_USAGE` 常量无返回路径）。

---

## 六、下一步第一件事（M5 启动）

1. 实装 `gui/app.py`（PySide6 四页签），复用 `pipeline.compute_full_calc`，GUI 层零判定逻辑（AST 守门断言）。
2. 实装 `report/`（Markdown + XLSX 导出，含免责声明 + 参数来源块），与 GUI/CLI 共用。
3. PyInstaller onedir 双 exe + 中立目录 `env -i` CLI 五连；收尾落盘 HANDOFF-M6。

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

# 基准（M2 起；M4 扩 B4/B5）
py -X utf8 tools/bench.py                 # 达标 exit 0 / 未达标 exit 1
py -X utf8 tools/bench.py --json          # 结构化指标（写 README 用）
py -X utf8 tools/bench.py --only B4       # 单跑一项（未知名 → exit 2）

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
| R-03 | 不定时工作制法定节假日加班费 | ✅ 已闭环（D-41） |
| R-04 | 试点地区选择 | ✅ 已闭环（D-35） |
| R-06 | 技术报告是否出 docx 版 | ⬜ M5 定夺 |
