# HANDOFF-M6：M5 桌面交付 → M6 发布

> 交接快照（ai-tool-project-sprint 阶段 0）。**新对话续接用法**：
> `/goal 读取 "plan/HANDOFF-M6.md" 继续完成任务`（入库文件内一律写相对路径）。
> 快照日期：2026-10-13 ｜ 上一里程碑：**M5 桌面交付** ｜ 下一棒：**M6 发布**

---

## 一、当前进度（M5 已完成什么）

### 1.1 GUI 实装（`code/src/lcc/gui/app.py`）

7 个页签：**四类计算**（经济补偿/赔偿金、加班费、未休年休假、二倍工资）+ **参数库** + **报告** + **适用依据**。
输入表单覆盖全部 `EmploymentFacts` / `TerminationFacts` 字段，含「计算」「重置为示例」「导出 Markdown」
「导出 XLSX」四个动作。门控拦截（如广东 440000 仍 pending）时把错误展示在页签与状态栏，**不崩溃、不留空窗**。

**GUI 层零判定逻辑**（D-13 / FR-8.2）由三条 AST 断言守门（`code/tests/test_gui_layer.py`）：

| 断言 | 内容 |
|---|---|
| 不 import 规则层 | 禁止 `lcc.engine` / `lcc.params` / `lcc.gate` / `lcc.law` / `lcc.model` / `lcc.benchmark` / `lcc.decimalutil` |
| 无算术运算 | `BinOp` 且两侧操作数均非字符串字面量的 `*` `/` `-` `//` `%` `**` |
| 无政策数值 | `21.75` / `365` / `150` / `200` / `300` / `1.5` / `2.0` / `3.0` |

**落实时的即时收益**：GUI 起初 `from ..model import CaseInput` 做输入校验，被第一条断言拦下 →
改走 `pipeline.build_case()`，CLI 一并收口 → **输入格式解释全项目只剩一份实现**。

### 1.2 编排上收（M5-1）

`lcc.pipeline` 的公开入口扩为 6 个，CLI 与 GUI 共用：

```
build_case(raw)           输入校验（表现层不 import lcc.model）
build_request(case, ...)  构造请求（默认模块集合只有一处定义）
compute_full_calc(req)    计算
parameter_overview()      参数库概览（CLI params / GUI 参数库页签）
clause_overview()         条款库概览
diagnostics()             环境自检（CLI doctor 的数据源）
```

`code/tests/test_pipeline_orchestration.py` 断言**行为一致**（不是"两处都调了 pipeline"这种字面声明）：
CLI stdout 金额 = pipeline 直调字段 = 报告章节金额；同一输入两次调用逐字段一致。
CLI 的 `cmd_params` / `cmd_doctor` 也改为消费 pipeline 入口，`cli.py` 不再 import `params` / `law` / `data_paths`。

### 1.3 报告导出（M5-3，FR-6）

**结构**：`report/__init__.py`（stdlib-only：`report_sections()` + Markdown）
与 `report/xlsx.py`（**唯一可选依赖边界**，守卫式惰性导入 openpyxl）。

**单一渲染源**：Markdown 与 XLSX 都消费 `report_sections()` 的章节结构 →
FR-6.1 的「两格式内容一致」成为**结构性质**而非人工比对。

报告必含（均有测试）：输入事实 / 参数来源块（发布机关 + 年度 + 文号 + URL + 抓取日期）/
逐项计算过程（直接渲染引擎 `steps` 留痕，报告层不重算）/ 适用依据 / 免责声明。

**XLSX 确定性落盘（实测踩坑 + 修复）**：`openpyxl` 的 `save_workbook()` 在写盘瞬间把
`docProps/core.xml` 的 `dcterms:modified` **无条件覆盖为当前 UTC 时刻**（openpyxl 3.1.5
`writer/excel.py:292`），zip 条目时间戳亦取当前时间 → 同一输入两次导出**字节不同**。
修复：保存后调 `_canonicalize_archive()` 读出全部条目、归一化两个时间戳、以固定时间戳 +
`create_system=0` 重打包。`test_xlsx_export_is_byte_reproducible` 守门（无修复必失败）。

> 教训：文档初稿先写了「XLSX 可复现」，实测 sha256 不同；定位后修复并**把结论改成实测结果**。
> 凡是"应当可复现"的断言，都要有一次 sha256 实测背书。

### 1.4 打包（M5-5）

| 项 | 内容 |
|---|---|
| spec | `tools/lcc-cli.spec`（`console=True`）、`tools/lcc-gui.spec`（`console=False`） |
| datas 单一源 | 两者均调 `lcc.packaging.build_datas()`，**不内联清单** |
| 入口脚本 | `tools/entry_cli.py`、`tools/entry_gui.py`（GUI 入口在无控制台时用原生消息框报错） |
| 构建编排 | `tools/build_release.py`（校验白名单 → 构建 → 自动验证） |
| 产物验证 | `tools/verify_package.py`（中立目录 + 最小环境） |

**`lcc.packaging` 放在包内的原因**：顶层名 `packaging` 会**遮蔽 PyPI 的 `packaging`**
（PyInstaller 自身依赖它做版本判断）；且「装到哪」（`build_datas`）与「从哪找」
（`data_paths`）是同一件事的两面。

**实测踩坑（重要）**：PyInstaller **5.13.2**（本机 3.8 自带）在扫描 PySide6 6.6 字节码时抛
`TypeError: 'Instruction' object is not iterable` → **GUI 打包必须用 PyInstaller ≥ 6**。
本机用 `py -3.12`（PyInstaller 6.22.3）。spec 内对 5.x/6.x 属性差异用
`getattr(a, "zipped_data", [])` 兜底，同一份 spec 两版本都能跑。

**中立目录验证实测结果**：

```
== CLI 五连（最小环境）==
[OK] params（exit 0）
[OK] doctor（exit 0）
[OK] calc --modules severance（exit 0）
[OK] calc（默认四模块）（exit 0）
[OK] calc --preview（exit 1）
[OK] report --output *.md（exit 0）
[OK] report --output *.xlsx（exit 0）
== GUI 冒烟（offscreen）==
[OK] lcc-gui: GUI 已启动（offscreen 下运行至主动终止）
PACKAGE_VERIFY_OK
```

> **发布构建的解释器必须先装 `openpyxl`**：否则打包出的 exe 不具备 README 承诺的 XLSX 能力
> （会走降级通路 exit 1）。验证脚本对两种情况都断言——有依赖须产出文件，无依赖须明确提示。
> 从冻结 exe 导出的 Markdown 与 XLSX 均逐字节可复现（sha256 两次一致，XLSX 哈希与源码态相同）。

> **验证脚本的一处必要处理**：`_stdio._ensure_utf8_stdio()` 的纪律是「流自身能编码中文就保持原样」，
> 故本机中文控制台（cp936）下 exe 按 **GBK** 输出，CI（cp1252 管道）下才转 UTF-8。
> `verify_package.py` 必须按 UTF-8 → locale 依次尝试解码，否则会把"编码不同"误判为"内容不符"。

### 1.5 演示素材（M5-4）

`tools/make_demo_assets.py` → `docs/demo/`：8 张页签 PNG + 1 个循环 GIF。

- **字体**：Qt 6 起不再随附字体，offscreen 平台不扫描系统字体目录 → 中文渲染成豆腐块。
  脚本按候选路径显式加载 CJK 字体（Windows 优先 Microsoft YaHei）。
- **可复现**：固定帧序 / 窗口尺寸 / GIF 时长与调色板，不写当前时间。
  **实测两次独立生成的 9 个文件 sha256 全部一致**。

### 1.6 技术报告（M5-6）

`docs/技术报告.md` 十节：问题与定位 / 架构 / 口径判定规则化 / 参数库版本化 /
日历唯一来源 / 基准体系 / 桌面交付 / 验证体系 / 已知边界 / 口径速查。

**R-06 已闭环（跳过 docx）**：GitHub 原生渲染 Markdown；docx 会引入第二份真相与转换漂移风险。

### 1.7 CI 接线

`.github/workflows/ci.yml` 从 8 步扩到 12 步，新增：

- `env: QT_QPA_PLATFORM: offscreen`（job 级）；
- `Install (dev + gui + report extras)`——**关键**：不装 PySide6/openpyxl 会让 GUI 与 XLSX
  用例静默跳过（假绿）；
- `Qt system libraries (Linux)`：`libegl1 libxkbcommon-x11-0 libxcb-cursor0`；
- `Report export smoke (Markdown + XLSX)`；
- `GUI offscreen smoke`（`tools/gui_smoke.py`，真实构造窗口 + 触发计算 + 导出报告）。

### 1.8 M5 完成判据（已实测达成）

> GUI 四页签可跑且零判定逻辑（AST 守门）；报告导出含免责声明与参数来源；
> 双 exe 在中立目录 + `env -i` 下 CLI 五连通过；技术报告入仓。

### 1.9 验证证据（M5 收尾实跑）

- 全量 pytest：**214 用例**（收集数）；**3.12 全量 212 passed + 2 skipped**（skip 为未装
  openpyxl，属预期）；**3.8 分批逐文件全通过**（14 个测试文件；全量单次偶发退出期 segfault 139）。
- 五道门禁：`NO_POLICY_LITERALS_OK`（11 文件 0 命中）/ `FROZEN_RULESETS_OK` /
  `FROZEN_TRUTH_OK` / `DESSENSITIZE_AUDIT_OK`（tracked）。
- 基准全达标：B1 9/9、B2 406/406、B3 5/5、B4 96/96、B5 40/40、阳性对照 4/4。
- CLI 冒烟：`params` / `doctor` / `calc --modules severance` / `calc`（四模块）exit 0；
  `calc --preview` exit 1。
- GUI offscreen 冒烟：7 页签齐备、四模块页签有内容、报告页签含免责声明、两种格式导出成功。
- 打包验证：`PACKAGE_VERIFY_OK`（见 §1.4）。
- 素材可复现：9 文件 sha256 两次一致；XLSX 导出 sha256 两次一致。

---

## 二、M6 待办（下一棒做什么）

| # | 任务 | 关键点 |
|---|---|---|
| M6-1 | 脱敏四步 + 产物本体扫描 + 提交元数据邮箱检查留档 | `dessensitize_audit.py --mode history` 全历史复核；邮箱改写须在**已建仓后**用 filter-branch/reflog expire/gc（D-28） |
| M6-2 | 干净环境（新 clone + 新 venv）按 README 逐字跑通 | 含 `[dev,gui,report]` extras 安装；`QT_QPA_PLATFORM=offscreen` 跑 GUI 测试 |
| M6-3 | CI 首跑全绿；push 数 = run 数对账 | 本次 M5 推送将触发首跑 |
| M6-4 | GitHub 建仓公开 + Release（exe + 演示 GIF）+ topics | 仓库已存在（D-36），故为补 Release |
| M6-5 | 发布物本体验证（下载 → sha256 一致 → 中立目录自检） | 用 `tools/verify_package.py --dist <解压目录>` |
| M6-6 | README 状态行转正 + 「下载即用」+「已知环境问题」节 | 已知环境问题至少含：PyInstaller 5.x 不能打 GUI、offscreen 中文字体需显式加载 |

> **M6 完成判据（建议）**：全历史脱敏 0 命中；干净环境按 README 逐字跑通；
> CI 全绿且 push 数 = run 数；Release 附双 exe + GIF，下载后 sha256 与本地一致且中立目录自检通过。

---

## 三、既定口径清单（动了会打挂基准/测试的约定）

1. **真值语义**：`expected` 主期望 + `also_expect` 隐含结论；对账按"全部非 pass 字段集"；语义**单一实现源** `lcc/benchmark/cases.py`。
2. **不许改真值凑引擎**：发现口径错误改引擎 + 加测试。**检查器谓词自身不自洽**时可改谓词（D-39）；**真值语义本身口径错误**须**引擎与真值同源修正**（D-42）。判据均为 `gen_cases.py --check` 仍 `FROZEN_TRUTH_OK`。
3. **Decimal 口径**：JSON `parse_float=Decimal`；金额量化两位 `ROUND_HALF_UP`；天数记录精度 6 位。年休假应休未休天数**向下取整**（D-31）；年限余日 ≥15 天计 0.5 月（D-34）。
4. **status 门控单点**：只有 `gate.effective_ruleset()` 产出可计算规则集；引擎签名只接受 `EffectiveRuleset`。
5. **坐标精确匹配**：`load_ruleset` 不做模糊/回退；跨坐标必须报错。
6. **零政策字面量**：法定数值只来自数据包；`tools/check_no_literals.py` 扫描 engine/benchmark/gui/pipeline（含 docstring/注释）。**新增代码前先看 `BANNED_TOKENS`**（当前禁用：21.75 / 365 / 150·200·300 及其百分号形态 / 1.5·2.0·3.0）。
7. **退出码**：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误；`--preview` 命中门控 → exit 1 且不进入引擎。`tools/bench.py` 亦遵此三语义。
8. **测试全离线**：零网络、零 API、无外部 mock。
9. **冻结产物纪律**：`data/rules/*` 与 `data/truth/*` 均为生成器产出，**禁手改**；文本 `write_bytes` + `\n`。
10. **引擎层不得 import CLI/GUI**；核心层零第三方依赖（D-09）。
11. **日历唯一来源**：日期类型判定只在 `ruleset.holiday_day_type()`（四类），引擎不得自建日历逻辑。
12. **引擎输出含 `amount`**：四引擎输出均含 `amount` 字段，CLI/报告据此判定"有无金额"。
13. **基准分层**：B2 样本驱动；**B4/B5 规则驱动**（不读真值库）；新增基准须进 `_BENCHMARK_KEYS` 以支持 `--only`。
14. **编排单点（M5 起）**：表现层只经 `lcc.pipeline` 的公开入口；**GUI 不得 import 规则层**（AST 守门）；默认模块集合只在 `pipeline.MODULES` 一处定义。
15. **可选依赖纪律**：核心层零第三方；`cli.py` / `gui/` / `report/xlsx.py` 允许**函数内 + try/except ImportError** 的守卫式惰性导入。新增可选依赖须同步 `test_repo_gates.py` 的白名单。
16. **导出可复现（M5 起）**：报告 Markdown 与 XLSX 均须同一输入逐字节一致；XLSX 保存后必须走 `_canonicalize_archive()` 归一化时间戳与 zip 元数据。

### 三.1 月工资口径（D-32）

`monthly_wages` 单序列同时服务经济补偿/年休假/加班费/二倍工资，约定为**「应得工资、剔除加班工资」**。

### 三.2 加班基数与工时制度（D-33 / D-41）

- 加班基数 = 劳动者月工资（12 个月平均，不低于最低工资），**地区无关**。
- 倍率**一律由日历日期类型 + 常数包**决定，**不随 `work_system` 变化**；`work_system` 为记录性字段。

### 三.3 日历三字段

`holiday_calendar` 三字段：`days`（法定节假日，最高档）/ `rest_days`（调休休息日，次档）/ `adjusted_workdays`（调休上班日，次档）；其余为 `workday`（最低档）。缺 `rest_days` 会系统性少算（D-37）。

### 三.4 年休假取整（D-31）

取整方向 = **向下取整**，作用于**「应休未休天数」最终量**（`floor(折算应休天数 − 当年度已安排天数)`），下限截 0；折算应休天数本身保留原值。**累计不满 1 年 → 应休 0 天**（D-42）。

### 三.5 二倍工资区间（plan/04 §6）

起算 = 用工满 `start_after_months` 个月的**次日**（月末夹取）；硬性截止 = 用工满 `start_after_months + max_months` 个月之日；区间月数 = `_months_and_remainder(start, end)[0] + 1`（首尾含当月）；`end < start` → 0 个月。

---

## 四、本机环境坑（全部实测）

- **本机有 3.8.8 与 3.12.10**（`py -0p`）：3.8 上 `pytest` 解析到 **8.3.5**；**别把"本机 3.12 能跑"当 3.8 证据**。
- **`py -X utf8` 是本机习惯、也是 CI 盲区**：入口 `_ensure_utf8_stdio()` 是必需品。
  **冻结 exe 的输出编码随环境变**（本机 cp936 → GBK；CI cp1252 管道 → UTF-8）——
  写验证脚本读 exe 输出时必须按 UTF-8 → locale 依次尝试解码。
- **pyc 偶发损坏 / 退出期 segfault**：全程 `PYTHONDONTWRITEBYTECODE=1`；
  若见 pytest 全绿但退出码 139，先 `find . -name __pycache__ -prune -exec rm -rf {} +` 再跑；
  仍不稳则**分批跑**（每文件一次，D-20）——M5 收尾 3.8 全量单次触发过两次 139，分批后 14 文件全通过。
- **PyInstaller 版本**：GUI 打包**必须 ≥ 6**（5.13.2 无法解析 PySide6 6.6 字节码）。
  本机 3.8 自带 5.13.2（只够打 CLI），3.12 装的是 6.22.3（两个都能打）→ 发布构建用 `py -3.12`。
- **Qt offscreen 中文字体**：offscreen 平台不扫描系统字体目录 → 截图/冒烟中文显示为豆腐块。
  需 `QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")` 并 `QApplication.setFont()`。
  CI Linux 需装 `libegl1 libxkbcommon-x11-0 libxcb-cursor0`。
- **Git Bash `/tmp` ≠ Python 的 `/tmp`**：给 CLI 传文件路径时用**仓库内相对路径**（如 `.scratch/x.json`）。
- **`--modules` 是 `nargs="+"`**：位置参数 `input` 必须写在 `--modules` **之前**。
- **pip 代理污染**：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- **venv 通道**：Git Bash 下用 `./.venv/Scripts/python.exe` 相对形式；`py` 启动器会绕过 venv。
- **数据目录显式传入不参与回退**（给错即报错）——刻意的，防假绿。
- **Windows 上别用 Python `open(...,"w")` 改源码做实验**：会把 `\n` 翻成 `\r\n`，触发 LF 门禁。
- **PyInstaller 的 `build/` 目录会留下大量 `__pycache__`**：跑测试前先清，否则可能读到陈旧字节码
  （M5 实测出现过 assert-rewrite 阶段崩溃，清掉 `build/`+`dist/` 后恢复）。

---

## 五、DoD 逐项核对（M5）

| # | DoD | 状态 | 证据 |
|---|---|---|---|
| M5-1 | `lcc.pipeline` 编排上收，CLI 与 GUI 共用同一编排（行为迁移前后一致） | ✅ | 6 个公开入口；`test_pipeline_orchestration.py` 10 项（含 CLI stdout = pipeline = 报告三方对账） |
| M5-2 | PySide6 多页签（四类计算 + 参数库 + 报告），GUI 层零判定逻辑（AST 守门） | ✅ | 7 页签；`test_gui_layer.py` 三条 AST 断言 + offscreen 冒烟（含门控失败路径） |
| M5-3 | 报告导出 Markdown + XLSX（含免责声明 + 参数来源块） | ✅ | `report_sections()` 单一渲染源；`test_xlsx_report_matches_markdown_content`、`test_markdown_report_contains_required_blocks` |
| M5-4 | offscreen 冒烟 + 演示素材（PNG + GIF）入 `docs/demo/` | ✅ | `tools/make_demo_assets.py` 9 文件；两次生成 sha256 全一致；`tools/gui_smoke.py` → `GUI_OFFSCREEN_SMOKE_OK` |
| M5-5 | PyInstaller onedir 双 exe；中立目录 + `env -i` CLI 五连通过 | ✅ | `dist/lcc-cli/lcc.exe` + `dist/lcc-gui/lcc-gui.exe`；`tools/verify_package.py` → `PACKAGE_VERIFY_OK`；`test_packaging.py` 8 项 |
| M5-6 | 技术报告 `docs/技术报告.md` 入仓 | ✅ | 十节；README 已挂链接；R-06 已闭环（跳过 docx） |

**偏差说明**：
1. 报告模块拆为 `report/__init__.py`（stdlib-only）+ `report/xlsx.py`（可选依赖边界）——
   使「零依赖导出通路」在结构上与「可选依赖通路」分离。
2. `lcc/packaging.py` 放包内（非 `tools/packaging.py`），理由见 §1.4。
3. 新增 `docs/demo/README.md`（素材清单 + 重新生成命令 + 脱敏说明），DoD 未要求但便于复核。
4. XLSX 确定性落盘修复（§1.3）为 M5 新增工程项，原 DoD 未列。

---

## 六、下一步第一件事（M6 启动）

1. 推 M5 提交到 `origin/main`，确认 CI 首跑全绿（12 步，含 GUI offscreen 冒烟与报告导出冒烟）；
2. `dessensitize_audit.py --mode history` 全历史复核 + 提交元数据邮箱检查留档；
3. 干净环境（新 clone + 新 venv）按 README 逐字跑通（含 `[dev,gui,report]`）；
4. 建 Release：上传 `dist/lcc-cli` / `dist/lcc-gui` 打包 zip + `docs/demo/demo.gif`，写 topics；
5. 下载发布物本体做 sha256 + 中立目录自检；README 状态行转正 + 补「下载即用」「已知环境问题」；
6. 收尾落盘 `plan/HANDOFF-FINAL.md`（末态基线 / 发布执行记录 / 复跑手册 / 遗留项，D-27）。

---

## 七、关键命令速查

```bash
# 环境（本机）
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=code/src          # 未 pip install -e 时需要
export QT_QPA_PLATFORM=offscreen    # GUI 测试/冒烟/素材生成需要

# 测试（双解释器）
py -X utf8 -m pytest code/tests -q
py -3.12 -X utf8 -m pytest code/tests -q
# 全绿但退出码 139 → 清缓存重跑；仍不稳则分批（逐文件）：
find . -name __pycache__ -type d -prune -exec rm -rf {} +
for f in code/tests/test_*.py; do py -X utf8 -m pytest "$f" -q; done

# 基准
py -X utf8 tools/bench.py                 # 达标 exit 0 / 未达标 exit 1
py -X utf8 tools/bench.py --json          # 结构化指标（写 README 用）
py -X utf8 tools/bench.py --only B4       # 单跑一项（未知名 → exit 2）

# 门禁五连
py -X utf8 tools/check_no_literals.py
py -X utf8 tools/gen_rulesets.py --check
py -X utf8 tools/gen_cases.py --check
py -X utf8 tools/dessensitize_audit.py --mode tracked
py -X utf8 tools/dessensitize_audit.py --mode messages
py -X utf8 tools/dessensitize_audit.py --mode history      # 发布前复核

# CLI
py -X utf8 -m lcc params
py -X utf8 -m lcc doctor
py -X utf8 -m lcc calc examples/sample-case.json --modules severance
py -X utf8 -m lcc calc examples/sample-case.json                    # 默认四模块 → exit 0
py -X utf8 -m lcc calc --preview examples/sample-case.json          # → exit 1
py -X utf8 -m lcc report examples/sample-case.json --output r.md    # Markdown
py -X utf8 -m lcc report examples/sample-case.json --output r.xlsx  # 需 openpyxl
py -X utf8 -m lcc gui                                               # 桌面界面

# M5 新增工具
py -X utf8 tools/gui_smoke.py                    # GUI offscreen 冒烟（CI 步骤）
py -X utf8 tools/make_demo_assets.py             # 生成 docs/demo 素材（PNG + GIF）
py -X utf8 tools/make_demo_assets.py --list      # 只列将产出的文件

# 打包（GUI 必须用 PyInstaller ≥ 6 → 本机 py -3.12）
py -3.12 -X utf8 -m pip install -e "./code[build]"
py -3.12 -X utf8 tools/build_release.py          # 构建两个 exe 并自动验证
py -X utf8 tools/verify_package.py               # 单独验证 dist/ 下的产物

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
| R-05 | 是否投赛事 | ✅ 已闭环（不投，D-01） |
| R-06 | 技术报告是否出 docx 版 | ✅ 已闭环（**跳过**；md 已入仓 `docs/技术报告.md`，需求触发再启动） |
