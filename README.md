# 劳动用工合规计算引擎

> 本地目录 `10-13-labor-compliance-calculator`（`10-13` = 2026-10-13 日期标签）。GitHub 仓库名发布时用纯净名 `labor-compliance-calculator`，见 [plan/00-README总览.md](plan/00-README总览.md)。

把经济补偿 N/N+1/2N 口径判定、加班费、年休假折算、二倍工资做成**参数化、可溯源、跨年度跨地区不混用**的本地引擎（桌面 exe + CLI）。

**核心特色**：`年度 × 地区` 版本化参数库 —— 切换地区与年度即切换计算参数，跨地区/跨年度混用**机制上报错**；每个结果旁挂法条条款依据与参数来源；未核对（`status=pending`）的参数**不得进入计算路径**。

## 状态

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 计划文档 00–06 + 可运行骨架（参数加载/坐标门控/status 门控/CLI/测试/CI） | ✅ 完成 |
| M1 | 数据先行：参数包逐条挂来源核对 + 条款库 + 合成档案真值库 + 台账 | ✅ 完成 |
| M2 | 经济补偿/赔偿金引擎（口径判定 + 三倍封顶 + 年限取整） | ✅ 完成 |
| M3 | 加班费 / 年休假 / 二倍工资引擎 | ✅ 完成 |
| M4 | 内置基准（口径判定 / 封顶取整边界 / 参数库自洽） | 🔄 B1/B2/B3 已跑通，M4 完善边界自洽扫描 |
| M5 | 桌面交付（PySide6 + PyInstaller + 报告导出 + 技术报告） | ⬜ |
| M6 | 脱敏发布 GitHub + Release | ⬜ |

> 当前：**M3 四引擎全部实现**。北京/上海 × 2025/2026 四个坐标的社平工资、最低工资、法定节假日日历已逐条核对官方原文并置 `status=verified`；法定常数包（21 条）与条款库（17 条）全部 verified；合成雇佣档案真值库 406 条入仓。**四引擎**：经济补偿/赔偿金（N / N+1 / 2N + 三倍封顶 + 12 年上限 + 最低工资下限 + 代通知金）、加班费（日历四类联动 + 三档倍率 + 工时制度）、未休年休假折算（分档 + 当年度折算 + 向下取整 + 冲抵）、未签书面劳动合同二倍工资（起算 + 11 个月上限 + 逐月明细）——406 条真值记录**四模块全部对账 0 mismatch**，基准 B1 100%。

## 特性

- **四类计算引擎**：经济补偿/赔偿金（N / N+1 / 2N 三口径判定 + 三倍封顶 + 12 年上限 + 最低工资下限 + 代通知金）、加班费（日历四类联动 + 三档倍率 + 工时制度区分）、未休年休假折算（分档 + 当年度折算 + 向下取整 + 300% 含已付 100% 的冲抵口径）、未签书面劳动合同二倍工资（起算 + 11 个月上限 + 逐月明细）。
- **`年度 × 地区` 参数库**：社平工资（三倍封顶基数）、最低工资标准、法定节假日日历（含调休）按坐标存储；文件名与内部坐标强一致校验。
- **口径登记**：社平工资口径（全口径城镇单位就业人员 / 城镇非私营在岗职工）逐地区登记 —— 多地口径已变更且是否用于封顶各地不一，**禁止跨地区套用**。
- **依据联动**：结论挂「法条条款 + 参数来源（哪年哪地社平工资 + 发布机关 + URL）」。
- **未核对不生效**：`status` 门控单点，`pending` 条目一律拒绝进入计算路径。
- **零政策字面量**：全部法定数值只能来自数据包；门禁脚本扫描引擎/基准/前端源码（含 docstring 与注释）。
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

# 预览模式：门控命中时仅展示参数元信息，不进入引擎、不输出金额（预期 exit 1）
python -m lcc calc --preview examples/sample-case.json
```

> 默认四模块全跑即得四引擎结论；`--modules` 可只跑指定模块。

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
  src/lcc/      核心包（params/gate/law/model/pipeline/engine/cli/report/gui）
  tests/        测试
tools/          生成器 / 门禁 / 审计脚本
docs/           技术报告与演示素材
```

## 评测指标

基准脚本 `tools/bench.py`（全离线、单次全量 < 1 秒）：退出码 0 达标 / 1 未达标。**当前 M3 实测全达标**。

| 基准 | 内容 | 目标 | 现状（M3 实测） |
|---|---|---|---|
| B1 口径判定 | 解除情形 → N/N+1/2N/none（含易混边界） | 100% | ✅ **9/9 = 100%** |
| B2 边界与全模块对账 | 真值库全量经**四引擎**重算（三倍 ±0.01、6 个月临界、12 年上限、余日 0/14/15 天、日历四类倍率、年休假分档与向下取整、二倍工资起算与 11 个月上限） | 全通过 | ✅ **406/406** |
| B3 参数库自洽 | 不存在坐标 / 年度回退 / 跨坐标混用 / pending 条目拦截 | 100% | ✅ **5/5 = 100%** |
| 阳性对照 | 已核对坐标必须放行（防"拦截率 100%"是"什么都拦"的空验） | 全通过 | ✅ **4/4** |

复跑：`python tools/bench.py`（或 `python tools/bench.py --json` 取结构化指标）。

**四引擎算例回归（M3-4）**：`data/truth/` 406 条记录经四引擎重算后，与真值语义（`lcc.benchmark.cases`，M1 冻结产物）逐字段 + 隐含结论对账 **0 mismatch**（两实现独立，`code/tests/test_truth_library.py` 的 `test_severance_engine_reconciles_all_truth_cases` / `test_m3_engines_reconcile_all_truth_cases` 守门）。

## 限制与边界

**首期不做**：工伤赔偿、社保公积金补缴计算、竞业限制补偿、股权激励、最低工资查询器、仲裁申请书代写、对接仲裁/法院系统。

**已知边界**：
- 法定节假日日历按年度发布，未发布年度的规则包保持 `pending`（门控拒绝，不假装可用）。
- 参数数值需逐地逐年核对，首期仅覆盖试点地区；其余地区机制完备但数据待核。
- 社平工资口径地区差异大，跨地区套用会在机制上被拒绝而非静默给出结果。

## 免责声明

本工具输出**仅供参考，不构成法律意见**；正式结论以劳动仲裁/法院裁判为准。所有计算均在本地完成，**不上传任何数据**。

## 许可

[MIT](LICENSE) © 2026 yuluo554