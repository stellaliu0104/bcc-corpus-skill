#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组装发行包 bcc-corpus.zip(维护者在仓库根目录运行)。

用法:
  python3 tools/package.py                 # 语料从 ../bcc-ai-tool-mac 取
  python3 tools/package.py --corpus <目录>  # 指定语料 txt 目录

要点:
- 用 Python zipfile 写包,非 ASCII 文件名强制带 UTF-8 标志位,
  避免 macOS 自带 zip 的中文乱码问题(Windows 解压必踩);
- 自动排除 venv/索引/配置/缓存,只保留代码+语料;
- 语料默认不入库,打包时从源项目拷入技能 data/Corpus。
"""

import argparse
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SKILL = os.path.join(REPO, "skill", "bcc-corpus")
DEFAULT_CORPUS = os.path.join(REPO, "..", "..", "bcc-ai-tool-mac",
                              "data", "Corpus")

EXCLUDE_PARTS = ("venv", "__pycache__", "CorpusIdx", ".git")
EXCLUDE_FILES = ("config.json",)  # 用户机器上首用引导,不预置配置
EXCLUDE_SUFFIX = (".pyc", ".zip")


def keep(rel):
    parts = rel.split(os.sep)
    if any(p in EXCLUDE_PARTS for p in parts):
        return False
    if os.path.basename(rel) in EXCLUDE_FILES:
        return False
    return not rel.endswith(EXCLUDE_SUFFIX)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=DEFAULT_CORPUS, help="语料 txt 目录")
    args = ap.parse_args()

    corpus = os.path.abspath(os.path.expanduser(args.corpus))
    if not os.path.isdir(corpus):
        print(f"语料目录不存在: {corpus}")
        sys.exit(1)

    dst = os.path.join(SKILL, "data", "Corpus")
    os.makedirs(dst, exist_ok=True)
    # 清掉旧语料,保证包内容与源一致
    for f in os.listdir(dst):
        os.remove(os.path.join(dst, f))
    n = 0
    for f in sorted(os.listdir(corpus)):
        if f.endswith(".txt"):
            with open(os.path.join(corpus, f), "rb") as src, \
                    open(os.path.join(dst, f), "wb") as out:
                out.write(src.read())
            n += 1
    print(f"语料就位: {n} 个文件")

    zip_path = os.path.join(REPO, "skill", "bcc-corpus.zip")
    entries = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(SKILL):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_PARTS]
            for fn in sorted(files):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, SKILL)
                arc = os.path.join("bcc-corpus", rel)
                if not keep(rel):
                    continue
                z.write(full, arc)  # 名字含非 ASCII 时 zipfile 自动置 UTF-8 标志
                entries += 1
    size = os.path.getsize(zip_path) / 1024 / 1024
    print(f"打包完成: skill/bcc-corpus.zip ({entries} 个条目, {size:.1f}M)")
    print("发给师门后: WorkBuddy 设置 → 技能 → 上传技能 → 拖入 zip")


if __name__ == "__main__":
    main()
