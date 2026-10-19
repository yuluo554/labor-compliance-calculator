# update 交接索引 — labor-compliance-calculator

> 诊断日期：2026-10-19
> 诊断方边界：只读诊断；未改任何受版本控制文件、未改 GitHub 状态、未发版、未改依赖。
> 唯一写入：本 `update/` 目录。

## 一句话结论

**建议迭代，产品面健康。** 225 项测试双解释器全绿、B1–B5 全达标且有空验防护、门控/坐标/退出码边界清晰、报告与附件打包都实测可复现、发布物经中立目录验收通过（PACKAGE_VERIFY_OK）。要修的是：`--preview` 语义与文档不一致（已核对坐标也被降级且文案错误）、发布产物多带 17 MB 无用依赖（PIL + lxml）、`[dev]` 计数三处写成 209 而实测 220、`build` extra 允许 PyInstaller 5.13 与 README 要求 ≥6 矛盾。

## 文件索引

| 文件 | 用途 |
|---|---|
| [00-诊断报告.md](00-诊断报告.md) | 现状基线、自述逐项实测、做得好的部分、缺陷 D1-D10、失效模式逐条结论 |
| [01-迭代路线.md](01-迭代路线.md) | 分批动作、每批门禁、范围边界、本仓库特有的坑 |
| [02-提示词-迭代对话.md](02-提示词-迭代对话.md) | 可直接复制到新对话的完整执行提示词 |
| `03-执行记录.md` | 由**执行方**新建；记录决策、每批命令/汇总行/退出码，状态「待复验」 |

## 需要用户拍板的决策

### D-1 `--preview` 的语义

| 方案 | 内容 | 收益 | 代价 | 建议 |
|---|---|---|---|---|
| **A** | 收窄为文档口径：**仅门控命中时**降级（已核对坐标 + `--preview` 正常出金额、exit 0）；notice 按状态分支 | 与 README/plan/03/plan/04 的现有描述一致；"预览"只在需要时接管 | 改变现有行为（已核对坐标加 preview 会出金额） | **推荐**（文档已这么写，改代码比改五处文档风险小） |
| B | 写实：保留"预览恒降级"（任意坐标 exit 1），改文档与退出码表；notice 分支文案 | 不改代码行为 | 要改 4 处文档 + 退出码表；已核对坐标也看不到金额，语义上"预览"过于强势 | 可选 |
| C | 保持现状不改 | 零改动 | 文档与实现继续不一致，用户看到"存在 pending 项"的错误说明 | 不推荐 |

> 实测证据：`lcc calc --preview examples/sample-case.json`（上海 2026，`规则包状态: [已核对]`）→ exit **1**、只出参数来源、文案说"参数条目存在未核对（pending）项"。

### D-2 运行时与打包口径

| 方案 | 内容 | 收益 | 代价 | 建议 |
|---|---|---|---|---|
| **A** | `requires-python >=3.12`；CI 去 3.8；`gui = PySide6>=6.12,<7`；`build = pyinstaller>=6.22,<7` | 与实测一致（py3.12 + Qt 6.12 → 225 passed；PyInstaller 6.22.3 → 双 spec 构建成功）；消除"extra 允许 5.13 但 README 要求 ≥6"的矛盾 | 排除 3.9–3.11 源码用户 | **推荐** |
| B | `>=3.11`；CI 加 3.11；其余同 A | 多覆盖一个受支持版本（3.11 至 2027-10） | 多一个矩阵；本次未在 3.11 实测 | 可选 |
| C | 保留 `>=3.8`，`build` 版本条件化（3.8 → 5.13 且只承诺 CLI；≥3.9 → 6.22） | 3.8 仍可用 | 继续背 EOL + 双 PyInstaller 分支 | 仅在用户要保 3.8 时 |

> 事实：3.8 EOL 2024-10-07；3.11 至 2027-10-31；3.12 至 2028-10-31。实测 PySide6 **6.12.0** 下 225 passed。

### D-3 版本与发布

| 方案 | 内容 | 收益 | 代价 | 建议 |
|---|---|---|---|---|
| **A** | 升 `0.1.1`（bugfix）；本地构建 + 验证；**经用户确认后**发布新 Release | 与"preview 语义修正 + 产物瘦身 + 文档回写"对应 | 需要用户打 tag/发 Release | **推荐** |
| B | 保持 0.1.0，只改仓库不发布 | 不涉及发布 | 已下载 0.1.0 的用户仍拿 38 MB CLI / 140 MB GUI 与错误文案 | 可选 |
| C | 升 0.2.0 并加新功能 | 大版本叙事 | 本轮定位是修正，混新功能放大验证面 | 不推荐 |

> 不要移动 tag `v0.1.0`；发布新版本时新建 tag。

## 本次迭代的边界

- **做**：`--preview` 语义收口（+测试）；两个 spec 排除 `PIL`/`lxml`（+构建后断言）；文档数字回写（`[dev]` 209 → 220、openpyxl 措辞）；`build` extra / `requires-python` / CI 矩阵口径统一；`.gitignore` 加 `_backups/`；`ledger` 错误引导。
- **不做**：改规则包数值/status、改引擎判定、改 B1–B5 阈值、改真值库、改退出码 0/1/2、改打包数据白名单、引入联网/LLM、发布（除非 D-3 选发布且用户执行）。
- **并行任务**：如果另一个对话在改别的仓库，本仓库只动本目录；不要跨仓库 `git add -A`。

## 起点基线（执行方不要重新论证）

- 路径：`D:\ProgramData\zcode\10-13-labor-compliance-calculator`
- HEAD：`2689a7fa3326f3e387ce87becee41b96178f2c8f`；tag `v0.1.0`；与 `origin/main` 0/0；工作树干净。
- HEAD 比 tag 多 **5 个纯文档提交**（`git diff --stat v0.1.0..HEAD` = 5 files / +64 / -19；`-- code/tests code/src` 为空）。
- 测试：收集 **225**；py3.12 **225 passed**（17.06 s）；py3.8 **225 passed**（18.99 s）；py3.12 + PySide6 **6.12.0** → **225 passed**；dev-only（`[dev]`）→ **220 passed / 5 skipped**。
- 基准：B1 9/9、B2 406/406、B3 5/5、B4 96/96、B5 40/40、阳性对照 4/4；退出 0。
- 门控：核算 4 verified / 8 份（京沪）；粤苏 4 份 pending；`calc` 广东 → exit 2；`--preview` → exit 1。
- 规则库：21 条常数全 verified；17 条条款；真值 406 条（320 + 86）。
- Release：CLI zip **18,949,021 B** sha256 `a750cb362597d7157b8ad064ceeca5e255472a5cd712f51049d81c7abf70635c`；GUI zip **60,412,182 B** sha256 `3f521dc300b0a7187bba5773626ad437cb74ecc05aac072bd445a1bdd03b7f67`；`demo.gif` 592,133 B。
- 发布物：解压后 CLI **38.4 MB / 54 条目**、GUI **140.3 MB / 1,125 条目**；其中 **PIL 10.7 MB + lxml 6.6 MB**（可去掉）。
- 发布物验收：`verify_package.py --dist` → **PACKAGE_VERIFY_OK**（CLI 五连 0/0/0/0/1 + 报告 MD/XLSX + GUI 起窗）。
- 打包可复跑：同一 dist 两次 `pack` → 两 zip sha256 完全一致。
- 报告可复现：两次 `report`（间隔 2 s）→ `report.md` 9,204 B / `report.xlsx` 14,543 B sha256 全同。
- 门禁：`NO_POLICY_LITERALS_OK`（11 文件）/ `FROZEN_RULESETS_OK` / `FROZEN_TRUTH_OK` / `DESSENSITIZE_AUDIT_OK`（tracked+messages+history）/ `RELEASE_ASSETS_SELFTEST_OK` / `DIST_SCAN_OK`（1,179 文件）。
- CI：最新 run `38473709151` 3 job 全 success；actions v4/v5 已收 Node20 弃用警告。
- 实测瘦身路径：py3.12 + PyInstaller 6.22.3，CLI spec 加 `excludes=["PIL","lxml"]` → 构建 rc 0、**21 MB / 30 文件**、无 PIL/lxml、`doctor` rc 0、XLSX 导出 rc 0（14,008 B）。