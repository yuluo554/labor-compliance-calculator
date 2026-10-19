# RELEASE-M6：脱敏发布与 Release 留档

> 里程碑：**M6 脱敏发布 GitHub + Release + 收尾固化** ｜ 快照日期：2026-10-13
> 纪律：本文件只写**实测命令与结论**；未跑的项目如实标 ⬜，不虚构。
> 留档文档自身用占位符指代敏感字面值，不复述（否则"全历史 0 命中"验证永远过不了）。

---

## 一、发布基线

| 项 | 值 |
|---|---|
| 仓库 | `yuluo554/labor-compliance-calculator`（public，SSH 远端） |
| 发布准备提交 | `167fe38`（M6 发布准备：可复跑附件打包 + 产物本体扫描 + 全历史脱敏守门 + README 两节） |
| 版本 | `0.1.0`（`code/pyproject.toml` 与 `code/src/lcc/__init__.py` 一致） |
| 产物构建解释器 | `py -3.12`（PyInstaller 6.22.3，PySide6 6.6.3.1，openpyxl 3.1.5） |
| 产物构建基线 | `dist/` 的 exe 构建于 `34be82e` 之后；`git diff 34be82e..167fe38 -- code/src tools/*.spec` **为空** → 产物与发布源码同运行时基线 |

---

## 二、脱敏四步 + 产物本体扫描（逐项留档）

| # | 步骤 | 命令 | 结论 |
|---|---|---|---|
| 1 | 敏感文件名 | `git ls-files` 人工核 + `.gitignore` 覆盖 `.env`/`*.key`/`*_private/`/运行产物 | ✅ 无 `.env`/`.key`/`secret`/`token` 类跟踪文件 |
| 2 | 内容级扫描（跟踪树） | `python tools/dessensitize_audit.py --mode tracked` | ✅ `DESSENSITIZE_AUDIT_OK`（0 硬门） |
| 2b | 提交信息扫描 | `python tools/dessensitize_audit.py --mode messages` | ✅ `DESSENSITIZE_AUDIT_OK`（0 硬门） |
| 2c | **全历史扫描** | `python tools/dessensitize_audit.py --mode history` | ✅ `DESSENSITIZE_AUDIT_OK`（0 硬门）；16 处 REVIEW 项全部为演示素材脚本**历史版本**里的 Windows 字体绝对路径，已于 `34be82e` 改为由 `WINDIR`/`SystemRoot` 环境变量推导 → 当前跟踪树 0 处 |
| 3 | 二进制样例 | 仓库内二进制仅 `docs/demo/*.png|gif`（示例输入渲染，虚构数据）与 `data/truth/*.json`（文本） | ✅ 无需单独扫（无 docx/xlsx 类含元数据样例入仓） |
| 4 | 已推送则重写历史 | **未触发**——内容级与元数据检查均在首次推送前已达标，无泄露需重写 | ✅ 无 force-push |
| 5 | **产物本体扫描** | `python tools/release_assets.py scan`（全 dist 树 1179 文件字节级） | ✅ `DIST_SCAN_OK`（工作根组合签名 0 命中、顶层禁区成分 0 命中） |
| 5b | 扫描器自证非空验 | `python tools/release_assets.py selftest` | ✅ `RELEASE_ASSETS_SELFTEST_OK`（阳性对照必中 + 阴性对照不误报） |

**发布前置·提交元数据邮箱**：`git log --all --format='%ae %ce'` 全历史唯一值 =
`282769740+yuluo554@users.noreply.github.com`（author 与 committer 两字段同值）→ **无需改写**。
守门测试 `test_commit_metadata_emails_are_noreply` 常驻（只查一个字段会让"改了一半"蒙混过关，故 ae/ce 都查）。

**产物本体扫描器实测踩坑（本轮新增，两条都是阳性对照抓出的真 bug）**：
1. 强标记的反斜杠最初在 Python 字面量里写成了**两个**字符（`"\\"` 的转义形态），
   而真实路径只有一个 → 阳性对照的"本机用户目录"形态**漏报**。修正为单反斜杠（字节子串匹配，非正则）。
2. 顶层禁区最初只查 `dist/` 顶层 → 实际 onedir 布局是 `dist/<name>/_internal/...`，
   植入的 `dist/<name>/plan` **漏报**。修正为逐产物查 `<name>/` 与 `<name>/_internal/` 两层
   （任意层级匹配则会把依赖包自带的 `tests/` 当命中——阴性对照已守门）。

> 另：本工具源码自身的注释里曾出现字面路径形态，被 `--mode tracked` 的无 git 兜底通道抓出（HARD 命中）——
> 与"扫描器源码也要过自己的扫描"纪律一致，已改写为不含字面路径的表述。

---

## 三、干净环境验证（新 clone + 新 venv，按 README 逐字）

环境：`git clone` 到仓库树外新目录（HTTPS 被网络策略重置 → 走 SSH 成功），`py -3.12 -m venv .venv`。

| 步骤 | 命令（README 原文） | 结论 |
|---|---|---|
| 建 venv | `py -m venv .venv` | ✅ 3.12.10；自带 pip 25.0.1 |
| 升 pip | `.venv/Scripts/python -m pip install -U pip` | ✅ 25.0.1 → 26.2.1 |
| 装依赖 | `.venv/Scripts/python -m pip install -e "./code[dev]"` | ✅ 可编辑安装成功（pyproject-only 项目） |
| 参数库 | `python -m lcc params` | ✅ exit 0，4 地区 / 8 规则包 / 状态正确 |
| 自检 | `python -m lcc doctor` | ✅ exit 0，`自检结论：骨架通路正常` |
| 计算（四模块） | `python -m lcc calc examples/sample-case.json` | ✅ exit 0 |
| 计算（单模块） | `python -m lcc calc examples/sample-case.json --modules severance` | ✅ exit 0 |
| 预览门控 | `python -m lcc calc --preview examples/sample-case.json` | ✅ exit 1（预览模式） |
| 门控拒绝 | 改 `input_facts.employment.region_code=440000` 后 `calc` | ✅ exit 2（3 个 pending 条目被拒） |
| 报告 Markdown | `python -m lcc report ... --output report.md` | ✅ exit 0，9204 字节 |
| 报告 XLSX | 装 `[report]` 后同上 `.xlsx` | ✅ exit 0，14008 字节 |
| 全量测试（`[dev]`） | `python -m pytest code/tests -q -rs` | ✅ **220 passed + 5 skipped**（跳过项 = 2 XLSX + 3 GUI，可选依赖缺席的声明式跳过；收集 225） |
| 全量测试（`[dev,gui,report]` + offscreen） | 同上 | ✅ **225 passed**（无跳过） |
| 收集数对账 | `pytest --collect-only -q` | ✅ `[dev]` 与装齐 extras **均收集 214→225 条**（GUI 用例是**函数级**跳过，不抹掉收集面） |
| 门禁五连 | `check_no_literals` / `gen_rulesets --check` / `gen_cases --check` / `dessensitize --mode tracked` / `release_assets selftest` | ✅ 全 OK |
| 基准 | `python tools/bench.py` | ✅ B1 9/9、B2 406/406、B3 5/5、B4 96/96、B5 40/40、阳性对照 4/4，exit 0 |
| GUI 冒烟 | `QT_QPA_PLATFORM=offscreen python tools/gui_smoke.py` | ✅ `GUI_OFFSCREEN_SMOKE_OK` |
| EOL 完整性 | 遍历 `data/` 查 `\r\n` | ✅ 0 文件含 CRLF（`.gitattributes` `* text=auto eol=lf` 生效） |
| 工作区 | `git status --short` | ✅ 干净（无被验证动作污染） |

> **`[dev]` vs `[dev,gui,report]` 两条通路分别跑**：README 快速开始只装 `[dev]`，
> GUI/报告章节另装 `[gui]`/`[report]` → 两条都对账（220+5 / 225），
> 差异**逐项指认**到声明式跳过，不是"双绿但悄悄少跑"。
>
> **历史留档说明**：本节数值为 **v0.1.0 发布时点记录**。v0.1.1 起 `--preview`
> 仅在门控命中时降级（已核对坐标照常出金额、exit 0），测试数增至 229（`[dev]`
> 为 224 passed + 5 skipped）。后续复测值见 `plan/HANDOFF-FINAL.md` 与
> `docs/技术报告.md`。

---

## 四、CI 对账（push 数 = run 数）

| 项 | 值 |
|---|---|
| **对账不变式** | **push 事件数 = CI run 数**（`gh run list --json event` 唯一值恒为 `push`，非 push 事件 run 数恒为 0）；唯一 head SHA 数 = push 事件数 − 1，因 `47415dc` 既有 main push 又有 tag push 两轮 |
| 复核方式 | `gh run list --limit 60 --json event --jq '[.[]\|select(.event=="push")]\|length'` 与 `gh run list --limit 60 --json databaseId --jq 'length'` 两值相等。**不钉固定总数**——此后每次回写提交都会 +1（回写提交只动文档，CI 仍照跑作常驻闸门，故两值始终同步增长） |
| 发布准备提交 | `167fe38` → run `38425953290`：三矩阵 **全 ✓ 225 passed** |
| 新增步骤实测 | `release_assets.py selftest` → `RELEASE_ASSETS_SELFTEST_OK`；`dessensitize --mode messages`/`--mode history` → 两模式 `DESSENSITIZE_AUDIT_OK`（依赖 `fetch-depth: 0`） |
| **首推终态提交失败并修复** | `edd9fcd` → run `38427285439` **三矩阵全红**：脱敏门抓到 `RELEASE-M6.md` 自身复述了字面路径形态（HARD `user_home_path`）→ 改为占位符表述，`--amend`（显式带 `GIT_COMMITTER_EMAIL`，防 committer 回落旧值）+ `--force-with-lease` 推送 |
| 修复后终态提交 | `47415dc` → run `38427732093`（main，三矩阵 **全 ✓**） |
| **tag 触发的那轮** | `v0.1.0` tag push → run `38428190360`（`head_branch=v0.1.0`，**success**）；`ci.yml` 配了 `tags: ["v*"]`，故 tag push 单独触发一轮 |
| 后续回写提交 | `265c41e` → `38428824426`、`1d9a9b6` → `38472400079`、`07c5622` → `38472889587`——均 **success**（回写提交只动文档，仍跑全量 CI 作常驻闸门） |
| 测试数（CI 实测） | windows/3.12、windows/3.8、ubuntu/3.12 均 **225 passed** |

> 说明：最早 7 个提交随"建仓首推"一次到达，只在其 tip 产生 1 个 run（D-36 已留档）；
> 此后每个 push 事件各触发 1 个 run。`edd9fcd` 已被 force-push 移出远端，其失败 run 保留在历史记录中
> （如实留档，不掩盖）。
>
> **本轮的教训与"留档不得复述敏感字面值"纪律吻合**：留档文档为解释"扫描器曾漏报"而复述了
> 字面路径形态 → 脱敏门当场拦下。处置即占位化表述；这也证明脱敏门**真的在 CI 里跑**（不是空验）。

---

## 五、发布附件台账（sha256 据链）

打包命令：`python tools/release_assets.py pack --out <仓库树外目录>`

| 附件（ASCII 名） | 字节数 | sha256 |
|---|---|---|
| `lcc-cli-0.1.0-win64.zip` | 18,949,021 | `a750cb362597d7157b8ad064ceeca5e255472a5cd712f51049d81c7abf70635c` |
| `lcc-gui-0.1.0-win64.zip` | 60,412,182 | `3f521dc300b0a7187bba5773626ad437cb74ecc05aac072bd445a1bdd03b7f67` |
| `demo.gif` | 592,133 | （演示素材，非安装包，不承诺字节确定） |

**可复跑性实测**：同一份 `dist/` 连续打包两次 → 两个 zip 的 sha256 **逐字节一致**
（`test_pack_is_byte_reproducible` 常驻守门）。区分两件事：
- **可复跑的是"打包这一步"**（同 dist → 同 zip 字节；固定 `date_time` + `create_system=0` + 条目按名排序）；
- **exe 构建这一步不保证字节确定**（PyInstaller 产物本身非字节确定）→ 留档不承诺 exe 哈希可复现。

---

## 六、发布物本体验证（下载件 → sha256 → 中立目录自检）

| 步骤 | 命令 | 结论 |
|---|---|---|
| 解压到中立目录（仓库树外） | 两个 zip 解压到同一目录 → `lcc-cli/` + `lcc-gui/` | ✅ |
| 中立目录 + 最小环境自检 | `python tools/verify_package.py --dist <解压目录>` | ✅ `PACKAGE_VERIFY_OK`：CLI 六连全过（`params`/`doctor`/`calc` 单模块/`calc` 四模块/`--preview` exit 1/`report` md + xlsx）+ GUI offscreen 冒烟启动 |
| **真下载**发布附件 | `gh release download v0.1.0 --repo yuluo554/labor-compliance-calculator` | ✅ 三个附件全部下载成功（`NO_PROXY="*"` 绕本机代理） |
| **下载件 sha256 与台账逐位一致** | `sha256sum *.zip` | ✅ `lcc-cli` = `a750cb36…70635c`、`lcc-gui` = `3f521dc3…7b7f67`（与 §五 留档值**逐位相同**） |
| **下载件解压到中立目录自检** | 解压下载的 zip → `verify_package.py --dist <该目录>` | ✅ `PACKAGE_VERIFY_OK`（与 §六第 2 行同法，对象是**用户实际下载到的那份**） |
| 版本一致性 | 解压后 `lcc.exe doctor` | ✅ 首行 `劳动用工合规计算引擎 v0.1.0 环境自检`（与 pyproject/`__init__` 一致） |

---

## 七、Release 与 topics

| 项 | 值 |
|---|---|
| tag | `v0.1.0`（annotated，指向终态提交 `47415dc`） |
| Release URL | https://github.com/yuluo554/labor-compliance-calculator/releases/tag/v0.1.0 |
| Release 附件 | `lcc-cli-0.1.0-win64.zip` / `lcc-gui-0.1.0-win64.zip` / `demo.gif` |
| topics | `annual-leave` `calculator` `cli` `compliance` `employment` `labor-law` `overtime` `pyside6` `python` `severance`（`gh api` 回读确认 10 个生效） |

---

## 八、发布执行结果

| # | 项 | 结果 |
|---|---|---|
| 1 | tag 触发 CI run | `38428190360`（`head_branch=v0.1.0`）**success** |
| 2 | 终态提交 CI run | `38427732093`（main）**success**，三矩阵全 ✓ |
| 3 | push 数 = run 数 | 不变式成立（push 事件数 = run 数；含 1 个失败后被 force-push 替换的 run，如实留档） |
| 4 | 下载件 sha256 | 与台账逐位一致（见 §六） |
| 5 | 中立目录自检 | `PACKAGE_VERIFY_OK`（对象为下载件解压目录） |
| 6 | topics 回读 | 10 个全部生效 |

### 八.1 发布后复核（GitHub 全新 clone = 远端最终提交）

| 项 | 结果 |
|---|---|
| clone head | `265c41e`（= 远端 `main` 最终提交） |
| README 逐字跑通（`[dev]`） | `python -m lcc params`/`doctor` exit 0；`pytest` **220 passed + 5 skipped** |
| README 逐字跑通（`[dev,gui,report]` + offscreen） | `pytest` **225 passed**；`calc` 四模块 exit 0、`--preview` exit 1、`report` md/xlsx 均 exit 0 |
| 历史三扫（对远端最终提交） | tracked/messages/history 三模式 `DESSENSITIZE_AUDIT_OK`（0 硬门） |
| 门禁 + 基准 | 零政策字面量 OK / 冻结规则包 OK / 冻结真值 OK / `selftest` OK / 基准**全部达标** |
| 仓库跟踪面 | 104 个跟踪文件；无 `dist/`/`build/`/`.venv`/scratch 类文件被跟踪 |

---

## 九、遗留与开放项

| # | 事项 | 状态 |
|---|---|---|
| 1 | 首发仅覆盖北京/上海 × 2025/2026 四个坐标；广东/江苏骨架 `pending`（机制完备，数据待核） | 设计边界（README 已述） |
| 2 | 法定节假日日历按年度发布，未发布年度保持 `pending` | 设计边界 |
| 3 | 技术报告 docx 版 | 显式跳过（R-06 已闭环；md 已入仓，需求触发再启动） |
| 4 | 缓议项 R-01~R-06 | **全部闭环**（D-30/D-31/D-41/D-35/D-01/R-06） |
