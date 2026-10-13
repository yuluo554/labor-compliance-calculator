"""``python -m lcc`` 入口（与 ``lcc`` 控制台脚本同一 main）。"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())