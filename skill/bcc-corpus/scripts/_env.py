# -*- coding: utf-8 -*-
"""公共环境工具:技能目录定位与跨平台 venv 解释器路径。

供 setup.py / launch_gui.py 复用,避免平台判定逻辑漂移(P0 审查项)。
"""

import os

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def venv_python(skill_root=None):
    """venv 内 python 解释器路径(win: Scripts/python.exe, 其余: bin/python)。"""
    root = skill_root or SKILL_ROOT
    return os.path.join(root, "venv", "Scripts", "python.exe") \
        if os.name == "nt" else os.path.join(root, "venv", "bin", "python")
