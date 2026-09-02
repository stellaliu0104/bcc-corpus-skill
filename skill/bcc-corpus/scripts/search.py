#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BCC 语料库检索 CLI —— WorkBuddy 技能「bcc-corpus」模式1 的执行入口。

子命令:
  freq     频率检索:   python search.py freq "a的n" [--number 500] [--top 30]
  context  语境检索:   python search.py context "很d" [--number 30] [--win-size 20]
  count    计数:       python search.py count "把n*v"
  compare  对比检索:   python search.py compare "很a" "非常a" [--top 20]

全局选项:
  --corpus PATH            语料目录(默认自动探测; 也可用环境变量 BCC_CORPUS)
  --wordlist name=词1 词2  预定义词表,可多次给出,供检索式 {$1=[name]} 引用
  --pretty                 美化 JSON 输出

输出: 单行 JSON(ok/elapsed_ms/...); 失败时 {"ok":false,"error":...,"hint":...}, 退出码 1。
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FREQ_TOP_DEFAULT = 30      # freq 返回给 agent 的条数上限(省上下文,全部数据在 stdout 可再取)
CONTEXT_NUMBER_DEFAULT = 30


def find_corpus(explicit):
    """按优先级探测语料目录: 显式参数 > BCC_CORPUS 环境变量 > 技能自带 > 兄弟源项目。"""
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("BCC_CORPUS"):
        cands.append(os.environ["BCC_CORPUS"])
    cands += [
        os.path.join(HERE, "data", "Corpus"),
        # 开发/测试回退: 本仓库与 bcc-ai-tool-* 同级时直接复用其语料与索引
        os.path.abspath(os.path.join(HERE, "..", "..", "..", "..",
                                     "bcc-ai-tool-mac", "data", "Corpus")),
        os.path.abspath(os.path.join(HERE, "..", "..", "..", "..",
                                     "bcc-ai-tool-win", "data", "Corpus")),
    ]
    for c in cands:
        if c and os.path.isdir(c):
            try:
                if any(f.endswith(".txt") for f in os.listdir(c)):
                    return os.path.abspath(c)
            except OSError:
                continue
    return None


def make_engine(corpus_abs):
    """LangSC 的 BCC 只接受相对路径(内部拼 './' 前缀),因此 chdir 到语料父目录。

    索引目录(CorpusIdx)与语料目录同级,这样可复用已有索引,避免每次重建。
    """
    parent = os.path.dirname(corpus_abs)
    name = os.path.basename(corpus_abs)
    os.chdir(parent)
    from bcc_engine import BCCEngine  # noqa: E402 (vendored, 同目录)
    return BCCEngine(name)


def parse_wordlists(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError(f"--wordlist 格式应为 name=词1 词2,收到: {it}")
        name, words = it.split("=", 1)
        out[name.strip()] = words.strip()
    return out


def err(msg, hint=None):
    payload = {"ok": False, "error": msg}
    if hint:
        payload["hint"] = hint
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="BCC 语料库检索 CLI")
    ap.add_argument("--corpus", default=None, help="语料目录")
    ap.add_argument("--wordlist", action="append", default=[],
                    metavar="NAME=词1 词2", help="预定义词表,可多次")
    ap.add_argument("--pretty", action="store_true", help="美化输出")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("freq", help="频率检索")
    p.add_argument("query")
    p.add_argument("--number", type=int, default=500)
    p.add_argument("--top", type=int, default=FREQ_TOP_DEFAULT)

    p = sub.add_parser("context", help="语境 KWIC 检索")
    p.add_argument("query")
    p.add_argument("--number", type=int, default=CONTEXT_NUMBER_DEFAULT)
    p.add_argument("--win-size", type=int, default=20)

    p = sub.add_parser("count", help="计数")
    p.add_argument("query")

    p = sub.add_parser("compare", help="对比两条检索式(频率+计数)")
    p.add_argument("query_a")
    p.add_argument("query_b")
    p.add_argument("--number", type=int, default=500)
    p.add_argument("--top", type=int, default=20)

    args = ap.parse_args()

    corpus = find_corpus(args.corpus)
    if not corpus:
        err("未找到语料目录",
            "请用 --corpus 指定包含 .txt 语料的目录,或让用户先运行 setup.py 导入语料。")

    t0 = time.time()
    try:
        eng = make_engine(corpus)
        for name, words in parse_wordlists(args.wordlist).items():
            eng.define_wordlist(name, words)
    except Exception as e:  # noqa: BLE001
        err(f"引擎初始化失败: {e}",
            "检查 LangSC 是否已安装(pip install LangSC==2.0.14)且语料目录下有 .txt 文件。")

    def elapsed():
        return int((time.time() - t0) * 1000)

    try:
        if args.cmd == "freq":
            r = eng.search_freq(args.query, number=args.number)
            records = r.get("records") or []
            out = {
                "ok": True, "type": "Freq", "query": args.query,
                "total": r.get("Total", r.get("total")),
                "distinct": r.get("Distinct", r.get("distinct")),
                "top": records[: args.top],
                "returned": min(args.top, len(records)),
                "truncated": len(records) > args.top,
                "elapsed_ms": elapsed(),
            }
        elif args.cmd == "context":
            r = eng.search_context(args.query, number=args.number,
                                   win_size=args.win_size)
            records = r.get("records") or []
            out = {
                "ok": True, "type": "Context", "query": args.query,
                "total": r.get("total"), "approximate": r.get("approximate"),
                "records": records, "elapsed_ms": elapsed(),
            }
        elif args.cmd == "count":
            r = eng.count(args.query)
            out = {
                "ok": True, "type": "Count", "query": args.query,
                "total": r.get("Total", r.get("total")),
                "elapsed_ms": elapsed(),
            }
        else:  # compare
            items = []
            for label, q in (("A", args.query_a), ("B", args.query_b)):
                f = eng.search_freq(q, number=args.number)
                c = eng.count(q)
                recs = f.get("records") or []
                items.append({
                    "label": label, "query": q,
                    "count_total": c.get("Total", c.get("total")),
                    "freq_distinct": f.get("Distinct", f.get("distinct")),
                    "top": recs[: args.top],
                })
            out = {"ok": True, "type": "Compare",
                   "items": items, "elapsed_ms": elapsed()}
    except Exception as e:  # noqa: BLE001
        err(f"检索执行失败: {e}",
            "常见原因: ① 检索式语法错误——对照 references/bcc_syntax.md 检查 "
            "(`*`跨词通配/`~`恰好一词/条件写在`{}`内) ② 词表未定义 ③ 语料索引损坏,重跑导入。")

    print(json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
