#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导入语料(模式2):把 doc/docx/xlsx/md/txt 转换并标注成 BCC 语料。

用法:
  python import_corpus.py --source ~/Desktop/新语料
  python import_corpus.py --source ~/Desktop/新语料 --rebuild   # 导入后重建索引

输出: data/Corpus/*.txt(GBK,每行一句已分词标注);映射 data/_maps/*.map.tsv
"""

import argparse
import json
import os
import platform
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from preprocess import process_file  # noqa: E402 (vendored,同目录)

# 注:.xls(Excel 97-2003) openpyxl 不支持,诚实排除;用户请先另存为 .xlsx
EXTS = (".doc", ".docx", ".xlsx", ".md", ".txt")
OUT_DIR = os.path.join(SKILL_ROOT, "data", "Corpus")


def main():
    ap = argparse.ArgumentParser(description="导入语料到 BCC 语料库")
    ap.add_argument("--source", required=True, help="语料来源文件夹")
    ap.add_argument("--out", default=OUT_DIR, help="语料输出目录(默认技能 data/Corpus)")
    ap.add_argument("--rebuild", action="store_true",
                    help="导入后删除旧索引,下次检索时自动重建")
    args = ap.parse_args()

    out_dir = os.path.abspath(os.path.expanduser(args.out))
    map_dir = os.path.join(os.path.dirname(out_dir), "_maps")
    # 映射文件绝不能放进语料目录(BCC 会索引目录下所有文件)

    src = os.path.abspath(os.path.expanduser(args.source))
    if not os.path.isdir(src):
        print(json.dumps({"ok": False,
                          "error": f"来源目录不存在: {src}"}, ensure_ascii=False))
        sys.exit(1)

    files = [os.path.join(root, fn)
             for root, _, fns in os.walk(src)
             for fn in fns if os.path.splitext(fn)[1].lower() in EXTS]
    if not files:
        print(json.dumps({"ok": False, "error": "目录里没有可导入的文件",
                          "supported": list(EXTS)}, ensure_ascii=False))
        sys.exit(1)

    # 旧版 .doc 仅 macOS 可转(系统 textutil);其它平台明确跳过并告知转换方法,
    # 而不是导入中途报错(跨平台一致性,P0 审查项)
    skipped_legacy = 0
    if platform.system() != "Darwin":
        docs, files = ([f for f in files if f.lower().endswith(".doc")],
                       [f for f in files if not f.lower().endswith(".doc")])
        skipped_legacy = len(docs)
        for f in docs:
            print(f"[skip] {os.path.basename(f)}: 旧版 .doc 请先用 Word/WPS "
                  f"另存为 .docx 再导入")
        if not files:
            print(json.dumps({"ok": False, "skipped_legacy_doc": skipped_legacy,
                              "error": "只有旧版 .doc 文件,请先批量另存为 .docx"},
                             ensure_ascii=False))
            sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(map_dir, exist_ok=True)

    ok, fail, total_sents = 0, 0, 0
    t0 = time.time()
    for i, path in enumerate(files, 1):
        try:
            info = process_file(path, out_dir, map_dir=map_dir)
            ok += 1
            total_sents += info["sentences"]
            print(f"[{i}/{len(files)}] {info['name']}: {info['sentences']} 句")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{i}/{len(files)}] ✗ {os.path.basename(path)}: {e}")

    if args.rebuild:
        idx = os.path.join(os.path.dirname(out_dir), "CorpusIdx")
        if os.path.isdir(idx):
            try:
                shutil.rmtree(idx)
            except OSError as e:
                print(json.dumps({"ok": False,
                                  "error": f"删除旧索引失败(文件被占用?): {e}",
                                  "hint": "关闭正在使用语料库的程序后重试"},
                                 ensure_ascii=False))
                sys.exit(1)
            print("[rebuild] 已删除旧索引,下次检索自动重建")

    n_corpus = len([f for f in os.listdir(out_dir) if f.endswith(".txt")])
    print(json.dumps({
        "ok": fail == 0, "imported": ok, "failed": fail,
        "skipped_legacy_doc": skipped_legacy,
        "sentences": total_sents,
        "corpus_files_total": n_corpus,
        "elapsed_s": round(time.time() - t0, 1),
    }, ensure_ascii=False))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
