# 劳动用工合规计算引擎

[![CI](https://github.com/yuluo554/labor-compliance-calculator/actions/workflows/ci.yml/badge.svg)](https://github.com/yuluo554/labor-compliance-calculator/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/yuluo554/labor-compliance-calculator)](https://github.com/yuluo554/labor-compliance-calculator/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **v0.1.1** —— 修正 `--preview` 语义（仅门控命中时降级）、发布产物瘦身（去除 PIL/lxml）、文档数字回写。Windows 64 位双 exe 见 [Releases](https://github.com/yuluo554/labor-compliance-calculator/releases/latest)。
> 本地目录 `10-13-labor-compliance-calculator`（`10-13` = 2026-10-13 日期标签）；GitHub 仓库名用纯净名 `labor-compliance-calculator`，见 [plan/00-README总览.md](plan/00-README总览.md)。

把经济补偿 N/N+1/2N 口径判定、加班费、年休假折算、二倍工资做成**参数化、可溯源、跨年度跨地区不混用**的本地引擎（桌面 exe + CLI）。

**核心特色**：`年度 × 地区` 版本化参数库 —— 切换地区与年度即切换计算参数，跨地区/跨年度混用**机制上报错**；每个结果旁挂法条条款依据与参数来源；未核对（`status=pending`）的参数**不得进入计算路径**。

## 状态

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 计划文档 00–06 + 可运行骨架（参数加载/坐标门控/status 门控/CLI/测试/CI） | ✅ 完成 |
| M1 | 数据先行：参数包逐条挂来源核对 + 条款库 + 合成档案真值库 + 台账 | ✅ 完成 |
| M2 | 经济补偿/赔偿金引擎（口径判定 + 三倍封顶 + 年限取整） | ✅ 完成 |
| M3 | 加班费 / 年休假 / 二倍工资引擎 | ✅ 完成 |
| M4 | 内置基准（口径判定 / 封顶取整边界 / 参数库自洽 / 边界自洽扫描 / 双向对账） | ✅ 完成 |
| M5 | 桌面交付（PySide6 多页签 + 报告导出 + PyInstaller 双 exe + 技术报告） | ✅ 完成 |
| M6 | 脱敏发布 GitHub + Release | ✅ 完成 |

> 当前：**M6 发布完成**。北京/上海 × 2025/2026 四个坐标的社平工资、最低工资、法定节假日日历已逐条核对官方原文并置 `status=verified`；法定常数包（21 条）与条款库（17 条）全部 verified；合成雇佣档案真值库 406 条入仓。**四引擎**：经济补偿/赔偿金（N / N+1 / 2N + 三倍封顶 + 12 年上限 + 最低工资下限 + 代通知金）、加班费（日历四类联动 + 三档倍率 + 工时制度）、未休年休假折算（分档 + 当年度折算 + 向下取整 + 冲抵）、未签书面劳动合同二倍工资（起算 + 11 个月上限 + 逐月明细）——406 条真值记录**四模块全部对账 0 mismatch**。基准 **B1~B5 全部达标**（B4/B5 为规则驱动，不依赖真值库样本）。**桌面交付**：PySide6 多页签界面（四类计算 + 参数库 + 报告 + 依据），GUI 层零判定逻辑由 AST 断言守门；报告导出 Markdown + XLSX（同源渲染，含免责声明与参数来源块）；PyInstaller onedir 双 exe 经中立目录 + 最小环境 CLI 六连验证。

## 下载即用

无需安装 Python —— 从 [Releases](https://github.com/yuluo554/labor-compliance-calculator/releases/latest) 下载打包好的 Windows 64 位版本，解压后直接运行：

| 附件 | 内容 |
|---|---|
| `lcc-cli-0.1.1-win64.zip` | 命令行版（`lcc.exe`）：`params` / `doctor` / `calc` / `report` |
| `lcc-gui-0.1.1-win64.zip` | 桌面版（`lcc-gui.exe`）：四类计算 + 参数库 + 报告 + 依据，共 7 个页签 |

解压后 **保持整个目录完整**（`_internal/` 与 exe 同级，数据与依赖都在里面），不要只复制 exe 单文件。

```bat
:: 命令行版
lcc.exe params
lcc.exe calc examples\sample-case.json

:: 桌面版（双击即可）
lcc-gui.exe
```

校验下载件完整性（比对 Releases 页面公布的 SHA-256）：

```bat
certutil -hashfile lcc-cli-0.1.1-win64.zip SHA256
certutil -hashfile lcc-gui-0.1.1-win64.zip SHA256
```

> 打包产物由 `tools/release_assets.py` 生成：附件名 ASCII、固定时间戳 → 同一份 `dist/`
> 两次打包**逐字节一致**（可复跑）；`ledger` 子命令产出台账 JSON 供 Release 留档引用。
> 注意可复跑的是**打包这一步**——PyInstaller 重新构建 exe 本身不保证字节确定。

## 特性

- **四类计算引擎**：经济补偿/赔偿金（N / N+1 / 2N 三口径判定 + 三倍封顶 + 12 年上限 + 最低工资下限 + 代通知金）、加班费（日历四类联动 + 三档倍率 + 工时制度区分）、未休年休假折算（分档 + 当年度折算 + 向下取整 + 300% 含已付 100% 的冲抵口径）、未签书面劳动合同二倍工资（起算 + 11 个月上限 + 逐月明细）。
- **`年度 × 地区` 参数库**：社平工资（三倍封顶基数）、最低工资标准、法定节假日日历（含调休）按坐标存储；文件名与内部坐标强一致校验。
- **口径登记**：社平工资口径（全口径城镇单位就业人员 / 城镇非私营在岗职工）逐地区登记 —— 多地口径已变更且是否用于封顶各地不一，**禁止跨地区套用**。
- **依据联动**：结论挂「法条条款 + 参数来源（哪年哪地社平工资 + 发布机关 + URL）」。
- **未核对不生效**：`status` 门控单点，`pending` 条目一律拒绝进入计算路径。
- **零政策字面量**：全部法定数值只能来自数据包；门禁脚本扫描引擎/基准/前端源码（含 docstring 与注释）。
- **桌面 + CLI 双形态**：PySide6 多页签界面（四类计算 + 参数库 + 报告 + 依据）与 CLI 共用同一编排层，GUI 层零判定逻辑（AST 守门）；PyInstaller onedir 双 exe 经中立目录验证。
- **全本地、零上传、零 LLM**：所有结论由确定性规则产生，无网络调用，无 API 依赖。

## 快速开始

```bash
git clone https://github.com/yuluo554/labor-compliance-calculator.git
cd labor-compliance-calculator

# 建议使用虚拟环境（Windows）
py -m venv .venv
.venv/Scripts/python -m pip install -U pip
.venv/Scripts/python -m pip install -e "./code[dev]"

# 参数库概览（坐标清单 + 核对状态）
python -m lcc params            # 需先 export PYTHONPATH=code/src（或 pip install -e 后直接用 lcc）

# 环境与数据自检
python -m lcc doctor

# 运行测试
python -m pytest code/tests -q
```

> GUI 相关测试需要 `PySide6`（`./code[gui]`）并在无显示环境下设 `QT_QPA_PLATFORM=offscreen`；
> 未安装时这些用例会**跳过**（而非失败）。CI 显式装齐 `[dev,gui,report]`，确保它们真跑。

> **`lcc` 命令**：`pip install -e ./code` 之后可直接用 `lcc params`；未安装时用 `PYTHONPATH=code/src python -m lcc params`。
> **注意 `py` 启动器**：Windows 的 `py` 会绕过 venv 装到系统 Python —— venv 段落一律用 `python -m pip ...`。

### 计算与门控演示

M3 完成后，**已核对坐标可直接算出四模块金额**；未核对坐标仍被门控拒绝（退出码 2）。

```bash
# 已核对坐标（示例输入用上海 2026）→ 四模块引擎全出金额（exit 0）
python -m lcc calc examples/sample-case.json

# 只跑经济补偿（exit 0）
python -m lcc calc examples/sample-case.json --modules severance

# 未核对坐标（广东 440000 仍 pending）→ 门控拒绝（预期 exit 2，提示"未核对"）
python -m lcc calc examples/sample-case.json   # 把 region_code 改成 440000 复现

# 预览模式：只在门控命中时降级——未核对坐标仅展示参数元信息、不输出金额（预期 exit 1）
# 已核对坐标带 --preview 照常出金额（exit 0），与不带 --preview 一致
python -m lcc calc --preview examples/sample-case.json   # 上海 2026 已核对 → exit 0
```

> 默认四模块全跑即得四引擎结论；`--modules` 可只跑指定模块。

### 桌面应用

```bash
# 安装 GUI 依赖（PySide6）
py -X utf8 -m pip install -e "./code[gui]"

# 启动桌面界面（四类计算 + 参数库 + 报告 + 适用依据，共 7 个页签）
python -m lcc gui
```

界面只消费编排层 `lcc.pipeline` 的结果——**GUI 层零判定逻辑**由 `code/tests/test_gui_layer.py`
的 AST 断言守门（不 import 引擎/参数库/门控、不含算术运算、不含政策数值）。演示截图见
[`docs/demo/`](docs/demo/)（含页签截图与操作 GIF）。

### 报告导出

```bash
# Markdown（stdlib，无需任何第三方依赖）
python -m lcc report examples/sample-case.json --output report.md

# XLSX（需 openpyxl，extra `report`；缺失时提示回退 Markdown）
py -X utf8 -m pip install -e "./code[report]"
python -m lcc report examples/sample-case.json --output report.xlsx
```

两种格式由**同一份章节结构**渲染，内容天然一致；均含输入事实、逐项计算过程、
**参数来源块**（发布机关 + 年度 + 文号 + URL + 抓取日期）与免责声明。

### 打包为 exe

```bash
# 需要 PyInstaller ≥ 6（PySide6 6.6 的字节码在 5.x 上无法解析）→ 用 3.12
# 若要发布物支持 XLSX 导出，构建解释器还需装 openpyxl（否则 XLSX 通路走降级提示）
py -3.12 -X utf8 -m pip install -e "./code[build,report]"
py -3.12 -X utf8 tools/build_release.py            # 构建两个 exe 并自动验证
```

产物：`dist/lcc-cli/lcc.exe`（控制台）与 `dist/lcc-gui/lcc-gui.exe`（窗口）。
验证方式是把 onedir 目录复制到**中立目录**、用**最小环境**跑 CLI 六连
（`--preview` 已核对坐标期望 exit 0、门控命中期望 exit 1），详见 `tools/verify_package.py`。

## 目录结构

```
plan/           计划文档 00–06（题目/需求/架构/详设/数据计划/决策记录）
data/
  rules/        地区×年度参数包（生成器冻结产物，禁手改）
  constants/    全国法定常数包（倍率/天数分档/口径天数）
  law/          法条条款库（法律名 + 条号 + 要点）
  regions/      地区主数据（行政区划码 + 社平工资口径登记）
  truth/        合成雇佣档案 + 真值库（M1 起）
code/
  src/lcc/      核心包（params/gate/law/model/pipeline/engine/cli/report/gui/packaging）
  tests/        测试
tools/          生成器 / 门禁 / 基准 / 审计 / 打包 / 演示素材脚本
docs/           技术报告（技术报告.md）与演示素材（demo/）
```

**分层依赖单向向下**：表现层（`gui/`、`cli.py`、`report/`）→ 编排层（`pipeline`，唯一编排源）
→ 引擎层 → 规则层 → 数据层。核心层（引擎/规则/编排/Markdown 报告）**零第三方依赖**；
可选依赖（PySide6 / openpyxl）只允许出现在守卫式惰性导入里。三条约束都有 AST 守门测试。

## 评测指标

基准脚本 `tools/bench.py`（全离线、单次全量 < 1 秒）：退出码 0 达标 / 1 未达标 / 2 用法错误。**当前全量达标**。

| 基准 | 内容 | 目标 | 现状 |
|---|---|---|---|
| B1 口径判定 | 解除情形 → N/N+1/2N/none（含易混边界） | 100% | ✅ **9/9 = 100%** |
| B2 边界与全模块对账 | 真值库全量经**四引擎**重算（三倍 ±0.01、6 个月临界、12 年上限、余日 0/14/15 天、日历四类倍率、年休假分档与向下取整、二倍工资起算与 11 个月上限） | 全通过 | ✅ **406/406** |
| B3 参数库自洽 | 不存在坐标 / 年度回退 / 跨坐标混用 / pending 条目拦截 | 100% | ✅ **5/5 = 100%** |
| B4 参数推导边界扫描 | **不依赖真值库样本**：切换端点全部由规则表/常数包推出，±0.01 邻域断言（封顶/下限切换、年限取整、12 年上限、年休假分档、加班三档、二倍工资区间） | 全通过 | ✅ **96/96** |
| B5 双向对账 | 公式推导端点 vs 穷举扫描恢复切换点，两条独立路径互验 | 全通过 | ✅ **40/40** |
| 阳性对照 | 已核对坐标必须放行（防"拦截率 100%"是"什么都拦"的空验） | 全通过 | ✅ **4/4** |

复跑：`python tools/bench.py`（或 `python tools/bench.py --json` 取结构化指标；`--only B4` 单跑一项）。

> **B4/B5 非空验**：测试内用阳性对照注入语义漂移（封顶 `>`→`>=`、年限阈值 `>=`→`>`、年休假分档下界、二倍工资首月）并断言基准**必须报失败**——`code/tests/test_bench.py` 的 `test_b4_detects_cap_switch_drift` / `test_b5_detects_year_rounding_drift` 守门。

**四引擎算例回归（M3-4）**：`data/truth/` 406 条记录经四引擎重算后，与真值语义（`lcc.benchmark.cases`，M1 冻结产物）逐字段 + 隐含结论对账 **0 mismatch**（两实现独立，`code/tests/test_truth_library.py` 的 `test_severance_engine_reconciles_all_truth_cases` / `test_m3_engines_reconcile_all_truth_cases` 守门）。

### M5 桌面交付验证

| 项 | 验收方式 | 现状 |
|---|---|---|
| GUI 零判定逻辑 | AST 断言：不 import 引擎/参数库/门控、无算术运算、无政策数值 | ✅ `code/tests/test_gui_layer.py` |
| GUI offscreen 冒烟 | offscreen 平台构造真实窗口 + 触发计算 + 导出报告 | ✅ `tools/gui_smoke.py`（CI 独立步骤） |
| 编排一致性 | CLI 输出 = pipeline 直调 = 报告章节，同一输入逐字段一致 | ✅ `code/tests/test_pipeline_orchestration.py` |
| 报告两格式一致 | Markdown 与 XLSX 消费同一章节结构（单一渲染源） | ✅ `test_xlsx_report_matches_markdown_content` |
| 导出可复现 | 同一输入两次导出 XLSX **逐字节一致**（归一化 openpyxl 写盘时间戳与 zip 元数据） | ✅ `test_xlsx_export_is_byte_reproducible` |
| 双 exe 中立目录验证 | 复制到临时中立目录 + 最小环境跑 **CLI 六连 + 报告导出**（含 `--preview` 已核对 0 / 门控命中 1） | ✅ `tools/verify_package.py` → `PACKAGE_VERIFY_OK` |
| datas 白名单单一源 | 两个 spec 均调 `lcc.packaging.build_datas()`，不内联清单 | ✅ `code/tests/test_packaging.py` |
| 演示素材可复现 | 两次独立生成的 9 个文件 sha256 全部一致 | ✅ `tools/make_demo_assets.py` |

**测试规模**：229 个用例（Python 3.12.10 实跑全通过；Python 下限 3.12，3.8 已 EOL）。

技术报告（架构 / 口径判定规则化 / 参数库版本化 / 基准体系 / 桌面交付 / 验证体系）见
[`docs/技术报告.md`](docs/技术报告.md)。

## 限制与边界

**首期不做**：工伤赔偿、社保公积金补缴计算、竞业限制补偿、股权激励、最低工资查询器、仲裁申请书代写、对接仲裁/法院系统。

**已知边界**：
- 法定节假日日历按年度发布，未发布年度的规则包保持 `pending`（门控拒绝，不假装可用）。
- 参数数值需逐地逐年核对，首期仅覆盖试点地区；其余地区机制完备但数据待核。
- 社平工资口径地区差异大，跨地区套用会在机制上被拒绝而非静默给出结果。

## 已知环境问题

从源码构建或运行开发环境时会遇到的环境坑（均为实测记录，非项目逻辑缺陷）：

| 现象 | 原因与处置 |
|---|---|
| GUI 打包报 `TypeError: 'Instruction' object is not iterable` | **PyInstaller 5.x 无法解析 PySide6 6.6 的字节码** → GUI 打包必须用 PyInstaller ≥ 6（本仓库用 3.12 + PyInstaller 6.x；3.8 自带的 5.13 只够打 CLI）。 |
| offscreen 下截图/界面中文显示为方块（豆腐块） | Qt 6 起不再随附字体，且 offscreen 平台不扫描系统字体目录 → 需显式 `QFontDatabase.addApplicationFont(...)` 加载 CJK 字体（Windows 优先 `msyh.ttc`）。CI Linux 还需装 `libegl1 libxkbcommon-x11-0 libxcb-cursor0`。 |
| 解压后只复制 exe 单文件 → 报缺数据/缺 DLL | PyInstaller **onedir** 产物：`_internal/` 必须与 exe 同目录，**整目录保持完整**。 |
| `py -m pip install ...` 装到了系统 Python（venv 内没有） | Windows 的 `py` 启动器**绕过 venv** → venv 段落一律用 `python -m pip ...`（激活后 `python` 才指向 venv）。 |
| 导出 XLSX 报缺 `openpyxl`（exit 1） | XLSX 是可选能力：源码态装 `./code[report]`；官方 Release 的 exe 已把 openpyxl 收进 PyInstaller 归档（PYZ），不出现在 `_internal/` 顶层目录。缺失时**明确提示并降级**，不崩溃。 |
| 冻结 exe 输出中文在部分终端乱码 | exe 的输出编码随环境变（本机 cp936 → GBK；CI cp1252 管道 → UTF-8）；入口 `_ensure_utf8_stdio()` 按编码探针决定是否转 UTF-8。读 exe 输出时按 UTF-8 → locale 依次尝试解码。 |
| `pytest` 全绿但退出码 139 | 本机 3.8 的偶发退出期 segfault（与用例无关）→ 清 `__pycache__` 重跑；仍不稳则**分批逐文件**跑。 |
| GUI 测试被静默跳过 | 未装 PySide6/openpyxl 时相关用例跳过（非失败）→ 要真跑请装 `./code[dev,gui,report]` 并设 `QT_QPA_PLATFORM=offscreen`（CI 即如此配置）。 |

## 免责声明

本工具输出**仅供参考，不构成法律意见**；正式结论以劳动仲裁/法院裁判为准。所有计算均在本地完成，**不上传任何数据**。

## 许可

[MIT](LICENSE) © 2026 yuluo554