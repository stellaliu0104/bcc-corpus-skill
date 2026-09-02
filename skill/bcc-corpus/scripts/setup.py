#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境自检与安装(模式1/2/3 的公共底座,win/mac 自适应)。

用法:
  python setup.py            # CLI 环境:venv + 最小依赖(LangSC/jieba/chardet)
  python setup.py --full     # 完整环境:再加 Streamlit GUI 依赖(模式3 需要)
  python setup.py --check    # 只检查不安装,输出 JSON 状态

安装位置:技能根目录下 venv/。语料目录:技能根目录下 data/Corpus。
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _env import venv_python  # noqa: E402 (跨平台 venv 路径)

SKILL_ROOT = os.path.dirname(HERE)
VENV = os.path.join(SKILL_ROOT, "venv")
CORPUS = os.path.join(SKILL_ROOT, "data", "Corpus")
CLI_DEPS = ["LangSC==2.0.14", "jieba>=0.42.1", "chardet>=7.0.0"]
GUI_DEPS = ["streamlit>=1.60.0", "pandas>=2.0.0", "openai>=1.0.0",
            "anthropic>=0.120.0", "python-dotenv>=1.0.0", "openpyxl>=3.1.0",
            "python-docx>=1.1.0", "requests>=2.31.0",
            "pywin32>=306; sys_platform == 'win32'"]


def check():
    have_venv = os.path.isfile(venv_python())
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if have_venv:
        out = subprocess.run([venv_python(), "--version"], capture_output=True,
                             text=True).stdout.strip()
        py_ver = out.replace("Python ", "") or py_ver
    ok_python = py_ver[:4].rstrip(".") in ("3.11", "3.12", "3.13")
    deps_cli = deps_gui = corpus = False
    if have_venv:
        r = subprocess.run([venv_python(), "-c",
                            "import LangSC, jieba, chardet"], capture_output=True)
        deps_cli = r.returncode == 0
        r = subprocess.run([venv_python(), "-c", "import streamlit, pandas"],
                           capture_output=True)
        deps_gui = r.returncode == 0
    if os.path.isdir(CORPUS):
        corpus = any(f.endswith(".txt") for f in os.listdir(CORPUS))
    return {
        "python": py_ver,
        "python_ok": ok_python,
        "venv_ready": have_venv,
        "deps_cli": deps_cli,
        "deps_gui": deps_gui,
        "corpus_ready": corpus,
        "corpus_path": CORPUS,
    }


def find_python():
    """按优先级找 3.11-3.13 的解释器:PYTHON 环境变量 > python3.13/12/11 > python3 > 当前。

    3.14 部分依赖可能无 wheel,但在能装上的平台(如本机)可用,
    因此仅在别无选择时携带 warning 使用,绝不静默选择过旧版本。
    """
    import shutil as _sh
    cands = []
    if os.environ.get("PYTHON"):
        cands.append(os.environ["PYTHON"])
    cands += ["python3.13", "python3.12", "python3.11", "python3"]
    for c in cands:
        path = _sh.which(c) or (c if os.path.isfile(c) else None)
        if not path:
            continue
        try:
            out = subprocess.run([path, "--version"], capture_output=True,
                                 text=True).stdout.strip()  # "Python 3.13.7"
            major, minor = (int(x) for x in out.split()[1].split(".")[:2])
        except Exception:  # noqa: BLE001
            continue
        if (major, minor) == (3, 14):
            continue  # 有更优选择时跳过 3.14
        if (major, minor) in ((3, 11), (3, 12), (3, 13)):
            return path, None
        if major >= 3 and minor >= 14:  # 未来的 3.15+ 同样降级为候选
            continue
    # 没找到受支持版本:回退当前解释器并给出警告
    return sys.executable, f"未找到 Python 3.11-3.13,回退使用 {sys.version.split()[0]};" \
        "若依赖安装失败,请从 python.org 安装 3.13 后重试"


def install(full):
    py, warning = find_python()
    print(f"[setup] 使用解释器: {py}", flush=True)
    if not os.path.isdir(VENV):
        print("[setup] 创建虚拟环境 ...", flush=True)
        subprocess.run([py, "-m", "venv", VENV], check=True)
    deps = CLI_DEPS + (GUI_DEPS if full else [])
    print(f"[setup] 安装依赖({len(deps)} 个包,约 2-8 分钟) ...", flush=True)
    subprocess.run([venv_python(), "-m", "pip", "install", "-q", "--upgrade",
                    "pip"], check=True)
    subprocess.run([venv_python(), "-m", "pip", "install", "-q", *deps],
                   check=True)
    st = check()
    print(json.dumps({"ok": True, **({"warning": warning} if warning else {}),
                      **st}, ensure_ascii=False, indent=2))


def main():
    if "--check" in sys.argv:
        print(json.dumps(check(), ensure_ascii=False, indent=2))
        return
    install("--full" in sys.argv)


if __name__ == "__main__":
    main()
