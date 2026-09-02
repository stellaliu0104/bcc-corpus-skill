#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""拉起 Streamlit 完整界面(模式3,兜底)。

用法: python launch_gui.py [--port 8501]

前置:需已运行 setup.py --full(GUI 依赖)。未安装时给出明确提示并退出。
"""

import argparse
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _env import venv_python  # noqa: E402 (跨平台 venv 路径)

APP_DIR = os.path.join(os.path.dirname(HERE), "app")


def main():
    venv_py = venv_python()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8501)
    args = ap.parse_args()

    if not os.path.isfile(venv_py):
        print("环境未就绪:请先运行 python scripts/setup.py --full")
        sys.exit(1)
    r = subprocess.run([venv_py, "-c", "import streamlit"], capture_output=True)
    if r.returncode != 0:
        print("GUI 依赖未安装:请先运行 python scripts/setup.py --full")
        sys.exit(1)

    url = f"http://localhost:{args.port}"
    proc = subprocess.Popen(
        [venv_py, "-m", "streamlit", "run", "app.py",
         "--server.port", str(args.port), "--server.headless", "true"],
        cwd=APP_DIR,
    )
    for _ in range(60):  # 最多等 60 秒
        time.sleep(1)
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    print(f"界面已启动: {url} (PID {proc.pid})")
                    print("在浏览器打开上述地址即可使用;关闭本窗口或按 Ctrl+C 退出。")
                    return
        except Exception:  # noqa: BLE001
            if proc.poll() is not None:
                break
    print("启动失败:请把以下输出发给维护者")
    sys.exit(1)


if __name__ == "__main__":
    main()
