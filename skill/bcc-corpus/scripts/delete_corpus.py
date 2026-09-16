#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除语料(模式4):从语料库中删除指定文件并清理映射文件。

用法:
  python delete_corpus.py --list                   # 列出所有语料文件（查看用）
  python delete_corpus.py --name 演讲_2024.txt      # 删除单个文件（精确匹配）
  python delete_corpus.py --pattern 演讲_2024*      # 按通配符批量删除
  python delete_corpus.py --name 演讲.txt --rebuild # 删除后重建索引

安全机制:
  - 默认先列出将要删除的文件清单，输出 ok:false + files_to_delete，等待确认
  - 加 --confirm 才真正执行删除
  - 删除 data/Corpus/*.txt 的同时清理 data/_maps/*.map.tsv 映射文件

输出: JSON (ok/deleted/skipped/corpus_files_total/...)
"""

import argparse
import fnmatch
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
CORPUS_DIR = os.path.join(SKILL_ROOT, "data", "Corpus")
MAP_DIR = os.path.join(SKILL_ROOT, "data", "_maps")


def find_corpus_dir():
    """和 search.py 相同的自动探测逻辑（优先技能自带目录）。"""
    candidates = [
        os.environ.get("BCC_CORPUS"),
        CORPUS_DIR,
        os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..",
                                     "bcc-ai-tool-mac", "data", "Corpus")),
        os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..",
                                     "bcc-ai-tool-win", "data", "Corpus")),
    ]
    for c in candidates:
        if c and os.path.isdir(c) and any(f.endswith(".txt") for f in os.listdir(c)):
            return os.path.abspath(c)
    return None


def list_corpus(corpus_dir):
    """返回语料目录下所有 .txt 文件名列表（排序）。"""
    return sorted(f for f in os.listdir(corpus_dir) if f.endswith(".txt"))


def match_files(corpus_dir, name=None, pattern=None):
    """根据精确名称或通配符找出匹配的文件名列表。"""
    all_files = list_corpus(corpus_dir)
    if name:
        # 精确匹配：允许用户省略 .txt 后缀
        target = name if name.endswith(".txt") else name + ".txt"
        return [f for f in all_files if f == target]
    if pattern:
        return [f for f in all_files if fnmatch.fnmatch(f, pattern)]
    return []


def find_map_file(map_dir, corpus_name):
    """找到对应的映射文件（名称去掉 .txt 后加 .map.tsv）。"""
    stem = corpus_name[:-4] if corpus_name.endswith(".txt") else corpus_name
    candidate = os.path.join(map_dir, stem + ".map.tsv")
    return candidate if os.path.isfile(candidate) else None


def err(msg, hint=None):
    payload = {"ok": False, "error": msg}
    if hint:
        payload["hint"] = hint
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="删除 BCC 语料库中的语料文件")
    ap.add_argument("--list", action="store_true",
                    help="列出所有语料文件（不删除任何内容）")
    ap.add_argument("--name", default=None,
                    help="要删除的文件名（精确匹配，可省略 .txt）")
    ap.add_argument("--pattern", default=None,
                    help="通配符批量匹配，如 '演讲_2024*'")
    ap.add_argument("--confirm", action="store_true",
                    help="确认执行删除（不加此项只预览，不真正删除）")
    ap.add_argument("--rebuild", action="store_true",
                    help="删除后重建索引（删除 CorpusIdx，下次检索时自动重建）")
    ap.add_argument("--corpus", default=None,
                    help="语料目录（默认自动探测）")
    args = ap.parse_args()

    # 确定语料目录
    corpus_dir = os.path.abspath(os.path.expanduser(args.corpus)) \
        if args.corpus else find_corpus_dir()
    if not corpus_dir:
        err("未找到语料目录",
            "请用 --corpus 指定包含 .txt 语料的目录，或先运行 setup.py 导入语料。")

    # --list 模式：只展示，不删除
    if args.list:
        files = list_corpus(corpus_dir)
        print(json.dumps({
            "ok": True,
            "corpus_dir": corpus_dir,
            "corpus_files_total": len(files),
            "files": files,
        }, ensure_ascii=False, indent=2))
        return

    if not args.name and not args.pattern:
        err("请指定 --name 或 --pattern",
            "示例: --name 演讲_2024.txt  或  --pattern '演讲_2024*'")

    if args.name and args.pattern:
        err("--name 和 --pattern 不能同时使用")

    # 匹配要删除的文件
    matched = match_files(corpus_dir, name=args.name, pattern=args.pattern)

    if not matched:
        hint = f"语料目录下没有匹配 {'名称 ' + args.name if args.name else '模式 ' + args.pattern} 的文件。"
        err("未找到匹配的语料文件", hint)

    map_dir = MAP_DIR if os.path.isdir(MAP_DIR) else \
        os.path.join(os.path.dirname(corpus_dir), "_maps")

    # 预览模式（不加 --confirm）：列出将要删除的内容，等待用户确认
    if not args.confirm:
        preview = []
        for fname in matched:
            map_file = find_map_file(map_dir, fname)
            preview.append({
                "corpus_file": fname,
                "map_file": os.path.basename(map_file) if map_file else None,
            })
        print(json.dumps({
            "ok": False,
            "preview": True,
            "message": f"以下 {len(matched)} 个文件将被删除，加 --confirm 确认执行",
            "files_to_delete": preview,
        }, ensure_ascii=False, indent=2))
        return

    # 执行删除
    t0 = time.time()
    deleted, skipped = [], []
    for fname in matched:
        corpus_path = os.path.join(corpus_dir, fname)
        try:
            os.remove(corpus_path)
            deleted.append(fname)
        except OSError as e:
            skipped.append({"file": fname, "reason": str(e)})
            continue

        # 清理对应映射文件（不存在时静默跳过）
        map_file = find_map_file(map_dir, fname)
        if map_file:
            try:
                os.remove(map_file)
            except OSError:
                pass

    # 可选：重建索引
    if args.rebuild and deleted:
        idx = os.path.join(os.path.dirname(corpus_dir), "CorpusIdx")
        if os.path.isdir(idx):
            try:
                shutil.rmtree(idx)
            except OSError as e:
                print(json.dumps({
                    "ok": False,
                    "error": f"删除旧索引失败: {e}",
                    "hint": "关闭正在使用语料库的程序后重试",
                    "deleted": deleted,
                }, ensure_ascii=False))
                sys.exit(1)

    remaining = list_corpus(corpus_dir)
    print(json.dumps({
        "ok": len(skipped) == 0,
        "deleted": len(deleted),
        "deleted_files": deleted,
        "skipped": len(skipped),
        "skipped_files": skipped,
        "corpus_files_total": len(remaining),
        "index_cleared": args.rebuild and bool(deleted),
        "elapsed_s": round(time.time() - t0, 2),
    }, ensure_ascii=False))
    sys.exit(1 if skipped else 0)


if __name__ == "__main__":
    main()
