# HANDOFF-FINAL：项目收官快照（M6 发布）

> 末态基线 / 发布执行记录 / 复跑手册 / 遗留项（D-27 命名约定）。
> 快照日期：2026-10-13 ｜ 末里程碑：**M6 脱敏发布 + Release + 收尾固化** ｜ 项目状态：**完结**
> 发布执行明细见 [RELEASE-M6.md](RELEASE-M6.md)；决策见 [06-决策记录.md](06-决策记录.md)。

---

## 一、末态基线

| 项 | 值 |
|---|---|
| 仓库 | `yuluo554/labor-compliance-calculator`（public，MIT） |
| 版本 | `0.1.0` |
| 发布准备提交 | `167fe38`（附件打包工具 + 产物扫描 + 全历史脱敏守门 + README 两节） |
| 终态提交 | 含本快照 + `RELEASE-M6.md` + D-45 + README/plan 状态行转正 |
| tag | `v0.1.0`（annotated，打在终态提交上） |
| Release 附件 | `lcc-cli-0.1.0-win64.zip` / `lcc-gui-0.1.0-win64.zip` / `demo.gif` |
| 测试规模 | **225 用例**（3.8.8 与 3.12.10 双解释器均实跑全通过；装齐 `[dev,gui,report]` 无跳过） |
| 基准 | B1 9/9、B2 406/406、B3 5/5、B4 96/96、B5 40/40、阳性对照 4/4 |
| 门禁 | 零政策字面量 / 冻结规则包 / 冻结真值 / 脱敏三模式 / 产物扫描 selftest —— 全 OK |

---

## 二、项目交付了什么

**劳动用工合规计算引擎**：把经济补偿 N/N+1/2N 口径判定、加班费、年休假折算、未签劳动合同二倍工资
做成参数化、可溯源、跨年度跨地区不混用的本地引擎（Windows 桌面 exe + CLI）。

| 能力 | 落点 |
|---|---|
| 四类计算引擎 | `code/src/lcc/engine/`（经济补偿/赔偿金、加班费、年休假、二倍工资） |
| `年度 × 地区` 参数库 | `data/rules/`（生成器冻结产物）、`data/constants/`、`data/regions/` |
| status 门控单点 | `lcc/gate.effective_ruleset()`；`pending` 一律拒绝进计算路径 |
| 依据联动 | `data/law/` 条款库 + 报告参数来源块（发布机关/年度/文号/URL/抓取日期） |
| 编排单点 | `lcc/pipeline`（6 个公开入口，CLI 与 GUI 共用） |
| 桌面 + CLI 双形态 | `lcc/gui/`（7 页签，AST 守门零判定逻辑）、`lcc/cli.py` |
| 报告导出 | `lcc/report/`（Markdown stdlib-only + XLSX 可选依赖边界，同源渲染、逐字节可复现） |
| 打包 | `tools/*.spec` + `lcc.packaging.build_datas()`（datas 单一源） |

---

## 三、发布执行记录

| # | 项 | 结论 |
|---|---|---|
| 1 | 脱敏四步（tracked / messages / history） | ✅ 三模式 `DESSENSITIZE_AUDIT_OK`，0 硬门 |
| 2 | 产物本体扫描（全 dist 树字节级） | ✅ 1179 文件 0 命中；`selftest` 阳性+阴性对照通过 |
| 3 | 提交元数据邮箱（ae/ce 两字段） | ✅ 全历史唯一值 = GitHub noreply，无需改写、无 force-push |
| 4 | 干净环境（新 clone + 新 venv，README 逐字） | ✅ `[dev]` 209+5skip、`[dev,gui,report]` 225 passed；门禁+基准+GUI 冒烟全过 |
| 5 | CI 全绿 + push 数 = run 数 | ✅ 13 run / 13 唯一 head SHA / 全 `push` 事件；run `38425953290` 三矩阵全 ✓ |
| 6 | 附件可复跑打包 + 台账 | ✅ 同 dist 两次打包 sha256 逐字节一致；ledger JSON 留档 |
| 7 | 发布物本体自检 | ✅ 解压仓库树外 → `verify_package.py --dist` → `PACKAGE_VERIFY_OK` |
| 8 | Release + topics | 见 §五（发布后回写） |

---

## 四、复跑手册（从零复现全部证据）

```bash
# 0) 环境（本机）
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=code/src
export QT_QPA_PLATFORM=offscreen        # GUI 测试/冒烟/素材需要

# 1) 测试（双解释器；3.8 若退出码 139 先清缓存再跑，仍不稳则分批逐文件）
py -3.12 -X utf8 -m pytest code/tests -q          # 期望 225 passed
py -X utf8 -m pytest code/tests -q                # 3.8，期望 225 passed

# 2) 门禁五连 + 产物扫描自证
py -X utf8 tools/check_no_literals.py
py -X utf8 tools/gen_rulesets.py --check
py -X utf8 tools/gen_cases.py --check
py -X utf8 tools/dessensitize_audit.py --mode tracked
py -X utf8 tools/dessensitize_audit.py --mode messages
py -X utf8 tools/dessensitize_audit.py --mode history     # 发布前复核
py -X utf8 tools/release_assets.py selftest

# 3) 基准
py -X utf8 tools/bench.py                                 # 期望 exit 0

# 4) CLI / 报告 / GUI 冒烟
py -X utf8 -m lcc params
py -X utf8 -m lcc calc examples/sample-case.json          # 四模块 exit 0
py -X utf8 -m lcc calc --preview examples/sample-case.json # exit 1
py -X utf8 -m lcc report examples/sample-case.json --output r.md
py -X utf8 tools/gui_smoke.py                             # GUI_OFFSCREEN_SMOKE_OK

# 5) 打包（GUI 必须 PyInstaller ≥ 6 → 本机 py -3.12）
py -3.12 -X utf8 -m pip install -e "./code[build,report]"
py -3.12 -X utf8 tools/build_release.py                   # BUILD_RELEASE_OK + PACKAGE_VERIFY_OK
py -X utf8 tools/release_assets.py scan                   # DIST_SCAN_OK
py -X utf8 tools/release_assets.py pack --out <仓库树外目录>  # RELEASE_PACK_OK
py -X utf8 tools/release_assets.py ledger --out <仓库树外目录>

# 6) 演示素材（可复现）
py -3.12 -X utf8 tools/make_demo_assets.py --out <仓库树外目录>
```

---

## 五、发布后复核（已完成）

| # | 项 | 结果 |
|---|---|---|
| 1 | tag | `v0.1.0`（annotated）→ 触发 run `38428190360`（`head_branch=v0.1.0`）**success** |
| 2 | 终态提交 CI | `47415dc` → run `38427732093`（main）**success**，三矩阵全 ✓ **225 passed** |
| 3 | Release URL | https://github.com/yuluo554/labor-compliance-calculator/releases/tag/v0.1.0 |
| 4 | 附件 | `lcc-cli-0.1.0-win64.zip`（18,949,021 B）+ `lcc-gui-0.1.0-win64.zip`（60,412,182 B）+ `demo.gif` |
| 5 | 下载件 sha256 复核 | 与台账**逐位一致**：cli `a750cb36…70635c`、gui `3f521dc3…7b7f67` |
| 6 | 下载件中立目录自检 | `verify_package.py --dist <解压目录>` → `PACKAGE_VERIFY_OK`；`lcc.exe doctor` 首行 `v0.1.0` |
| 7 | topics 回读 | 10 个全部生效 |
| 8 | push 数 = run 数 | 18 push 事件 = 18 run（其中 `47415dc` 有 main push + tag push 两轮；含 1 个失败后被 force-push 替换的 run，如实留档） |
| 9 | 一处修复实录 | 终态提交首推 `edd9fcd` 三矩阵全红——脱敏门抓到 `RELEASE-M6.md` 自身复述字面路径形态；占位化后 `--amend`（显式带 `GIT_COMMITTER_EMAIL`）+ `--force-with-lease` → `47415dc` 全绿 |
| 10 | 发布后 GitHub 全新 clone 复核 | clone head = 远端最终提交 `265c41e`；README 逐字跑通（`[dev]` 220+5skip、`[dev,gui,report]` **225 passed**）；历史三扫 0 硬门；门禁 + 基准全部达标 |

---

## 六、遗留项（开放但已定性）

| # | 事项 | 处置 |
|---|---|---|
| 1 | 首发仅北京/上海 × 2025/2026 四个坐标；广东/江苏骨架 `pending` | 设计边界：机制完备、数据待核（README 已述） |
| 2 | 法定节假日日历按年度发布，未发布年度保持 `pending` | 设计边界（门控拒绝，不假装可用） |
| 3 | 技术报告 docx 版 | 显式跳过（R-06 已闭环；md 已入仓，需求触发再启动） |
| 4 | 缓议项 R-01~R-06 | **全部闭环**（D-30 / D-31 / D-41 / D-35 / D-01 / R-06） |
| 5 | `pytest` 全绿但退出码 139（本机 3.8 偶发） | 环境级现象（清 `__pycache__` 或分批跑），非用例缺陷 |
| 6 | GitHub 事件时间线可能残留 force-push 记录 | 本项目**未做**任何历史重写/force-push，无此残留 |

---

## 七、下一棒（若续接）

项目已完结（M0–M6 全 ✅）。若要继续演进，方向按优先级：

1. **扩坐标**：按 `data/README.md` 台账逐地逐年核对官方原文，置 `status=verified` 即可进计算路径（机制已就绪，无需改代码）。
2. **参数库更新年度**：新年度日历/社平工资/最低工资发布后走 `tools/gen_rulesets.py` 重生成 + 台账登记。
3. **不定时工作制的地区差异**：若确认某地区确需差异，**逐地区登记到规则包**（不硬编码），按 D-41 追加决策。
4. **技术报告 docx 版**：需求触发时由 md 程序化生成（生成器入库，禁手改产物）。
