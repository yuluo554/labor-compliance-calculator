# HANDOFF-M1：M0 骨架 → M1 数据先行

> 交接快照（ai-tool-project-sprint 阶段 0）。**新对话续接用法**：
> `/goal 读取 "plan/HANDOFF-M1.md" 继续完成任务`（入库文件内一律写相对路径）。
> 快照日期：2026-10-13 ｜ 上一里程碑：**M0 骨架** ｜ 下一棒：**M1 数据先行**

---

## 一、当前进度（M0 已完成什么）

**计划文档 00–06 全部定稿**（`plan/`）：题目定义 v1、需求解读（FR-1~FR-8 / NFR-1~9 / 边界守卫）、架构与技术选型、模块详设（schema + 四引擎公式 + 门控 + 退出码）、数据计划与 M0–M6 DoD、决策记录（D-01~D-27 + 缓议 R-01~R-06）。

**可运行骨架已就位**：

| 组件 | 位置 | 状态 |
|---|---|---|
| 包骨架 + 版本 | `code/src/lcc/__init__.py`、`__main__.py` | ✅ |
| 编码守卫 | `code/src/lcc/_stdio.py` | ✅ cp1252 探针 reconfigure；cp936 不动 |
| 异常与退出码 | `code/src/lcc/errors.py` | ✅ 0/1/2 语义 |
| Decimal 口径 | `code/src/lcc/decimalutil.py` | ✅ `parse_float=Decimal`、`ROUND_HALF_UP` |
| 数据目录定位 | `code/src/lcc/data_paths.py` | ✅ 显式/env/冻结态/源码态分支 |
| 参数库（坐标 + schema） | `code/src/lcc/params.py` | ✅ 精确坐标、文件名↔内部坐标一致、verified 必挂来源 |
| **status 门控（单点）** | `code/src/lcc/gate.py` | ✅ `effective_ruleset()` 拒绝 pending |
| 条款库 | `code/src/lcc/law.py` | ✅ `resolve()` 缺 id 抛 `LawBasisError` |
| 输入模型 | `code/src/lcc/model.py` | ✅ 校验 + Decimal 化 |
| 编排层 | `code/src/lcc/pipeline.py` | ✅ CLI/GUI 共用（D-13） |
| 四引擎 | `code/src/lcc/engine/*.py` | 🔄 **仅声明 API + 公式依据，M2/M3 实现**（抛 `NotImplementedYet`） |
| CLI | `code/src/lcc/cli.py` | ✅ `params` / `doctor` / `calc`（含 `--preview`）/ `gui` |
| GUI / 报告 | `code/src/lcc/gui/`、`report/` | 🔄 M5 实现（惰性导入已就位） |
| 数据包 | `data/rules`(8) / `constants`(18 条) / `law`(16 条) / `regions`(4) | ✅ 结构入仓，**全 pending** |
| 生成器/门禁/审计 | `tools/gen_rulesets.py`、`check_no_literals.py`、`dessensitize_audit.py` | ✅ |
| 测试 | `code/tests/` 7 个模块 | ✅ **77 passed**（本机 3.8.8 与 3.12.10 双验） |
| CI | `.github/workflows/ci.yml` | ✅ 三矩阵（ubuntu/3.12、windows/3.12、windows/3.8） |

**验证证据（M0 收尾实跑）**：
- 本机 `py -3.8` 与 `py -3.12` 干净 venv：`pip install -e "./code[dev]"` 成功；`pytest code/tests` → **77 passed**，收集数 77（两版本一致）。
- 门禁三连：`NO_POLICY_LITERALS_OK` / `FROZEN_RULESETS_OK` / `DESSENSITIZE_AUDIT_OK`。
- CLI 冒烟：`params` exit 0；`doctor` exit 0；`calc examples/sample-case.json` **exit 2**（门控拦截，预期）；`calc --preview` **exit 1**（引擎待 M2，预期）。

---

## 二、M1 待办（下一棒做什么）

| # | 任务 | 关键点 |
|---|---|---|
| M1-1 | **选定试点地区**（≥2 省 × ≥2 年度）并核对社平工资/最低工资 | 写进 `data/README.md`；每值挂**发布机关 + 发布年度 + 口径 + URL + 抓取日期** |
| M1-2 | 法定常数包逐条核对官方原文 → `status=verified` + 补 `source` | 条号已挂（`data/constants/statutory-constants.json`），只需逐条回读原文确认数值 |
| M1-3 | 条款库逐条核对（条号与要点与官方原文一致）→ `verified` | 16 条已在库，`points` 为摘述（≤200 字，有守门测试） |
| M1-4 | 法定节假日日历按年度入库（含调休） | 国务院办公厅发布；填 `holiday_calendar.days` / `adjusted_workdays` |
| M1-5 | `tools/gen_cases.py` 合成档案 + 真值库 | **自研 splitmix64**（禁 stdlib `random`）；固定种子；逐字节一致守门 |
| M1-6 | `data/README.md` 台账更新（sha256 + 来源 + 核对结论） | 核对后 sha256 变，**三联动**更新（数据/台账/守门） |
| M1-7 | 「再生成逐字节一致」守门测试通过 | 现有 `test_frozen_rulesets_regenerate_byte_identical` 已覆盖 rules；真值库另配 |

**M1 完成判据**：至少一个 `(地区, 年度)` 坐标下全部条目 `verified`，且 `lcc calc` 能穿过门控进入引擎（此时会报 M2 未实现 —— 这本身就是门控已放通的证据）。

---

## 三、既定口径清单（动了会打挂基准/测试的约定）

1. **真值语义**：`expected` 主期望 + `also_expect` 隐含结论；对账按"全部非 pass 字段集"；语义**单一实现源** `lcc/benchmark/cases.py`（M1 建）。
2. **不许改真值凑引擎**：发现口径错误改引擎 + 加测试。
3. **Decimal 口径**：JSON `parse_float=Decimal`；金额量化两位 `ROUND_HALF_UP`（精度约定，豁免字面量门禁）；天数取整方向为**缓议项 R-02**，定稿前不得写死。
4. **status 门控单点**：只有 `gate.effective_ruleset()` 产出可计算规则集；引擎签名只接受 `EffectiveRuleset`。
5. **坐标精确匹配**：`load_ruleset` 不做模糊/回退；跨坐标必须报错。
6. **零政策字面量**：法定数值只来自数据包；`tools/check_no_literals.py` 扫描 engine/benchmark/gui/pipeline（含 docstring/注释）。**新增引擎代码前先看该脚本的 `BANNED_TOKENS`**。
7. **退出码**：0 成功 / 1 降级或计算非法 / 2 输入、坐标或门控错误（`code/tests/test_cli_exit_codes.py` 锁死）。
8. **测试全离线**：零网络、零 API、无外部 mock。
9. **冻结产物纪律**：生成器产出禁手改；文本 `write_bytes` + `\n`；未来 zip 型产物统一 `ZIP_STORED`+`create_system=0`+固定时间戳。
10. **引擎层不得 import CLI/GUI**；核心层零第三方依赖（两条 AST 守门测试）。

---

## 四、本机环境坑（全部实测）

- **本机有 3.8.8 与 3.12.10**（`py -0p`）：3.8 上 `pytest` 会被解析到 **8.3.5**（8.4+ 需 py≥3.9），`requires-python=">=3.8"` 下 `pytest>=7,<9` 约束正确；**别把"本机 3.12 能跑"当 3.8 证据**。
- **`py -X utf8` 是本机习惯、也是 CI 盲区**：本机中文控制台 cp936 能编码中文，所以代码里的非 ASCII 输出缺口会被掩盖 → 入口 `_ensure_utf8_stdio()` 是必需品（测试用 `cp1252` TextIOWrapper 复现）。
- **pyc 偶发损坏**：全程 `PYTHONDONTWRITEBYTECODE=1`；出怪错先清 `__pycache__` 再跑。
- **pip 代理污染**：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- **venv 通道**：Git Bash 下用 `./.venv/Scripts/python.exe` 相对形式可跑；`py` 启动器**会绕过 venv**装到系统 Python（README 里 venv 段落一律 `python -m pip`）。
- **`python -m lcc`** 需要 `__main__.py`（已加）；`pip install -e ./code` 后可直接用 `lcc` 命令。
- **数据目录显式传入不参与回退**（给错即报错）——这是刻意的：避免"以为指定了 A 实际用了 B"的假绿。

---

## 五、DoD 逐项核对（M0）

| # | DoD | 状态 | 证据 |
|---|---|---|---|
| M0-1 | plan/00–06 定稿、00 索引状态 ✅ | ✅ | `plan/` 六份文档；00 索引表已回写 |
| M0-2 | `pyproject.toml` 可 `pip install -e .`（extras） | ✅ | 3.8/3.12 干净 venv 各装成功 |
| M0-3 | `load_ruleset` 精确坐标；坐标不符抛错 | ✅ | `test_params.py::test_unknown_coordinate_raises` 等 5 项 |
| M0-4 | `validate` 拒绝缺来源的 verified、拒绝文件名↔坐标不一致 | ✅ | `test_validate_rejects_*` 4 项 |
| M0-5 | 门控拒绝 pending；`allow_pending` 不产金额 | ✅ | `test_gate.py` 5 项 |
| M0-6 | 条款库加载 + `resolve`；未知 id 抛错 | ✅ | `test_law.py` 7 项 |
| M0-7 | CLI `params`/`doctor`/`calc` | ✅ | CLI 冒烟 4 条命令 |
| M0-8 | 退出码 0/1/2 锁进测试 | ✅ | `test_cli_exit_codes.py` 15 项 |
| M0-9 | 数据包初始化（全 pending） | ✅ | 8 规则包 + 18 常数 + 16 条款 + 4 地区 |
| M0-10 | 零政策字面量门禁可跑 | ✅ | `NO_POLICY_LITERALS_OK`（8 文件 0 命中） |
| M0-11 | 全量 pytest 通过 | ✅ | 77 passed（3.8.8 与 3.12.10 双验） |
| M0-12 | CI 多矩阵 | 🔄 | workflow 已入仓 + 解析/接线守门测试通过；**尚未推送，CI 首跑待建仓后验证** |
| M0-13 | README 含简介/状态/快速开始/目录/免责 | ✅ | `README.md` |
| M0-14 | `plan/HANDOFF-M1.md` 落盘 | ✅ | 本文件 |

**偏差说明**：
- **M0-12 CI 首跑未验证**：仓库尚无远端（按 D-24 计划 M0 结束即建仓，可先私有）。workflow 的**可解析性**与 **fetch-depth: 0 接线**已由守门测试覆盖，但"CI 真的跑绿"需要建仓后才有证据 —— **这是 M1 启动前的第一件事**（见下）。
- **GUI 未实现**：属 M5 范围（plan/04 §9 明确 M0 不做）；`lcc gui` 已能正确报里程碑/缺依赖两种提示。

---

## 六、下一步第一件事（M1 启动前）

1. **建仓并接 CI**（D-24）：`gh repo create yuluo554/labor-compliance-calculator --public --description "..." --source . --remote origin`（**不带 `--push`**，避免 token 缺 `workflow` scope 的半失败态）→ `git remote set-url origin git@github.com:yuluo554/labor-compliance-calculator.git` → push 一次成（SSH 不受 OAuth scope 限制）。
2. 首推后 `gh run list` 对账 push 数 = run 数；三矩阵首跑绿（M0 已前置配置 eol=lf / 冻结 CR 守门 / extras 装齐 / py3.8 兼容写法，目标首跑即绿）。
3. 然后进入 M1 数据核对（先做 `tools/gen_cases.py` 与试点地区核对可并行）。

---

## 七、关键命令速查

```bash
# 环境（本机）
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=code/src          # 未 pip install -e 时需要

# 测试
py -X utf8 -m pytest code/tests -q

# 门禁三连
py -X utf8 tools/check_no_literals.py
py -X utf8 tools/gen_rulesets.py --check
py -X utf8 tools/dessensitize_audit.py --mode tracked
py -X utf8 tools/dessensitize_audit.py --mode messages     # 提交信息扫描
py -X utf8 tools/dessensitize_audit.py --mode history      # 全历史（建仓后复核用）

# CLI
py -X utf8 -m lcc params
py -X utf8 -m lcc doctor
py -X utf8 -m lcc calc examples/sample-case.json           # 预期 exit 2（门控拦截）
py -X utf8 -m lcc calc --preview examples/sample-case.json # 预期 exit 1（引擎待 M2）

# 规则包重生成（改了 regions.json 或年度区间后）
py -X utf8 tools/gen_rulesets.py

# 干净环境验证（发布门）
py -3.12 -m venv .venv-check && ./.venv-check/Scripts/python.exe -m pip install -e "./code[dev]"
```

---

## 八、缓议项（M1–M3 期间须闭环）

| 编号 | 事项 | 闭环时机 |
|---|---|---|
| R-01 | 代通知金（N+1）基数口径与是否受封顶约束 | M2 实现前（plan/04 §3.5 待补） |
| R-02 | 年休假当年度折算取整方向 | M3 实现前 |
| R-03 | 不定时工作制法定节假日加班费（多地仍付） | M3 前；无全国口径则参数化到规则包 |
| R-04 | 试点地区选择（≥2 省 × ≥2 年度） | **M1 启动时定** |
| R-06 | 技术报告是否出 docx 版 | M5 定夺（不做则显式记"跳过"） |