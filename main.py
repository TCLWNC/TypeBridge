#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CrossLink · 跨屏输入（电脑端）

    python main.py               打开界面
    python main.py --headless    只跑服务
    python main.py --tray        开机自启用（静默常驻托盘）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crosslink.app import main   # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
