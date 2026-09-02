#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能配置(当前仅一项: 结果存储目录)。

用法:
  python config.py                       # 查看当前配置(JSON)
  python config.py --results-dir <路径>   # 设置结果文件存储目录(需绝对/家目录展开)

SKILL.md 约定:首次导出前,agent 先问用户"检索结果文件想存在哪个文件夹?",
把用户选择保存进来;之后所有导出默认落在这个目录。
"""

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(SKILL_ROOT, "data", "config.json")

DEFAULTS = {"results_dir": ""}


def load():
    cfg = dict(DEFAULTS)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="bcc-corpus 技能配置")
    ap.add_argument("--results-dir", default=None,
                    help="结果文件存储目录(如 ~/Documents/BCC检索结果)")
    args = ap.parse_args()

    cfg = load()
    if args.results_dir is not None:
        path = os.path.abspath(os.path.expanduser(args.results_dir))
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            print(json.dumps({"ok": False, "error": f"目录不可创建: {e}"},
                             ensure_ascii=False))
            raise SystemExit(1)
        cfg["results_dir"] = path
        save(cfg)
        print(json.dumps({"ok": True, "results_dir": path,
                          "note": "已保存,之后导出默认存这里"}, ensure_ascii=False))
    else:
        print(json.dumps({"ok": True, **cfg,
                          "configured": bool(cfg["results_dir"])},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
