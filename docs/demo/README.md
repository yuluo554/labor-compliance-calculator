# 演示素材（docs/demo）

本目录的 PNG 截图与 GIF 由 `tools/make_demo_assets.py` **自动生成**（offscreen Qt 渲染），
**不手工编辑**——重跑即可复现（固定帧序、固定窗口尺寸、固定 GIF 时长与调色板）。

## 素材清单

| 文件 | 内容 |
|---|---|
| `01-input.png` | 输入事实表单（示例员工，虚构数据） |
| `02-severance.png` | 经济补偿/赔偿金页签：口径、年限、基数、金额与计算过程留痕 |
| `03-overtime.png` | 加班费页签：日历日期类型 → 三档倍率的逐条明细 |
| `04-annual-leave.png` | 未休年休假页签：分档、折算、向下取整、冲抵 |
| `05-double-wage.png` | 二倍工资页签：起算日、区间、逐月明细 |
| `06-params.png` | 参数库页签：地区主数据 + 规则包坐标与核对状态 + 条款库 |
| `07-report.png` | 报告页签：可导出测算说明（Markdown 与 XLSX 同源） |
| `08-basis.png` | 适用依据页签：每项结论的法律名 + 条号 + 要点 |
| `demo.gif` | 上述页签的循环演示（8 帧，每帧 1.4 秒） |

## 重新生成

```bash
# 需要 gui extra（PySide6）与 Pillow（GIF 合成）
py -X utf8 -m pip install -e "./code[gui]"
py -X utf8 -m pip install Pillow

py -X utf8 tools/make_demo_assets.py            # 全部生成到 docs/demo
py -X utf8 tools/make_demo_assets.py --list     # 只列出将产出的文件
py -X utf8 tools/make_demo_assets.py --no-gif   # 只出 PNG
```

## 脱敏说明

素材内容全部来自仓库内示例输入（`examples/sample-case.json`），员工身份为虚构
「示例员工」、工资为构造值，不含任何真实个人信息或企业数据。生成后由
`tools/dessensitize_audit.py --mode tracked` 复核（文本类扫描；素材为二进制，
不在其扫描面内）。
