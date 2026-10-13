# labor-compliance-calculator（包目录）

劳动用工合规计算引擎的 Python 包所在目录。**项目说明、快速开始、评测指标与免责声明见仓库根
[README.md](../README.md)。**

```
code/
├── pyproject.toml   打包配置（包名 labor-compliance-calculator，控制台脚本 lcc）
├── src/lcc/         核心包
└── tests/           测试
```

安装与运行：

```bash
# 从仓库根执行
python -m pip install -e "./code[dev]"
python -m pytest code/tests -q
```

> 本文件存在的原因：`pyproject.toml` 的 `readme` 字段相对于本目录解析，需有一个实际文件，
> 否则 sdist 构建会告警 "README.md cannot be found"。
