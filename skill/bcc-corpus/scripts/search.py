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
import csv
import json
import os
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FREQ_TOP_DEFAULT = 30      # freq 返回给 agent 的条数上限(省上下文,全部数据在 stdout 可再取)
CONTEXT_NUMBER_DEFAULT = 30
EXPORT_NUMBER = 5000       # 导出模式下单次拉取上限(安全阀)


def _has_txt(d):
    try:
        return any(f.endswith(".txt") for f in os.listdir(d))
    except OSError:
        return False


def find_corpus(explicit):
    """语料目录解析。

    语义(对语言学研究很关键,宁缺勿错):
      - 显式指定(--corpus)但无效 → 立即失败,绝不静默回退到别的语料库;
      - 未显式指定 → 依次尝试 BCC_CORPUS 环境变量 > 技能自带 > 兄弟源项目。
    """
    if explicit:
        if os.path.isdir(explicit) and _has_txt(explicit):
            return os.path.abspath(explicit)
        return None  # 显式但无效 → 由调用方报错
    for c in [os.environ.get("BCC_CORPUS"),
              os.path.join(HERE, "..", "data", "Corpus"),
              # 开发/测试回退: 本仓库与 bcc-ai-tool-* 同级时直接复用其语料与索引
              # (scripts → bcc-corpus → skill → bcc-corpus-skill → BCC document → 302-projects)
              os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..",
                                           "bcc-ai-tool-mac", "data", "Corpus")),
              os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "..",
                                           "bcc-ai-tool-win", "data", "Corpus"))]:
        if c and os.path.isdir(c) and _has_txt(c):
            return os.path.abspath(c)
    return None


def make_engine(corpus_abs):
    """LangSC 的 BCC 只接受相对路径(内部拼 './' 前缀),因此 chdir 到语料父目录。

    索引目录(CorpusIdx)与语料目录同级,这样可复用已有索引,避免每次重建。
    注意:chdir 有进程级副作用,本函数仅适用于一次性 CLI 进程,勿嵌入常驻服务。
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


# ── 结果导出(数据库式呈现:交互式 HTML 为默认,另支持 xlsx/csv) ───────

def _export_dir():
    """存储目录:读技能配置(data/config.json 的 results_dir)。

    未配置时不擅自选桌面等位置——返回 None,由调用方提示 agent 引导用户
    先运行 config.py --results-dir 选择目录(或本次用 --out 指定)。
    """
    cfg_path = os.path.join(HERE, "..", "data", "config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            d = os.path.expanduser(json.load(f).get("results_dir") or "")
        if d:
            os.makedirs(d, exist_ok=True)
            return d
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return None


def _rows_of(out):
    """把各种模式的输出统一成 (表头, 行列表, 分组标题列表)。"""
    t = out.get("type")
    if t == "Context":
        return ([("id", "序号"), ("keyword", "关键词"), ("left", "左文"),
                 ("right", "右文")],
                [[r.get("id"), r.get("keyword"), r.get("left"), r.get("right")]
                 for r in out.get("records") or []], None)
    if t == "Freq":
        total = out.get("total") or 0
        return ([("word", "词/搭配"), ("freq", "频次"), ("pct", "占比%")],
                [[r.get("word"), r.get("freq"),
                  round(100.0 * (r.get("freq") or 0) / total, 2) if total else 0]
                 for r in out.get("top") or []], None)
    if t == "Count":
        return ([("query", "检索式"), ("total", "命中总数")],
                [[out.get("query"), out.get("total")]], None)
    if t == "Compare":
        groups = []
        for it in out.get("items") or []:
            total = it.get("count_total") or 0
            groups.append((f"{it.get('label')}: {it.get('query')} (共{total})",
                           [("word", "词/搭配"), ("freq", "频次"), ("pct", "占比%")],
                           [[r.get("word"), r.get("freq"),
                             round(100.0 * (r.get("freq") or 0) / total, 2) if total else 0]
                            for r in it.get("top") or []]))
        return None, None, groups
    return None, None, None


def _export_xlsx(out, path):
    from openpyxl import Workbook
    headers, rows, groups = _rows_of(out)
    wb = Workbook()
    ws = wb.active
    ws.title = "检索结果"
    meta = [f"检索式: {out.get('query')}", f"命中总数: {out.get('total')}",
            f"导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "语料: 师门 BCC 演讲口传语料(jieba 分词标注)"]
    ws.append(meta)
    ws.append([])
    if groups:  # compare: 每组一个区块
        for title, hs, rs in groups:
            ws.append([title])
            ws.append([h[1] for h in hs])
            for r in rs:
                ws.append(r)
            ws.append([])
    else:
        ws.append([h[1] for h in headers])
        for r in rows:
            ws.append(r)
    wb.save(path)


def _export_html(out, path):
    headers, rows, groups = _rows_of(out)
    q = out.get("query") or ""
    total = out.get("total")

    def table_html(hs, rs, tid):
        head = "".join(f'<th onclick="sortT(\'{tid}\',{i})">{h[1]}▼</th>'
                       for i, h in enumerate(hs))
        body = "".join(
            "<tr>" + "".join(f"<td>{c if c is not None else ''}</td>" for c in r)
            + "</tr>" for r in rs)
        return (f'<table id="{tid}"><thead><tr>{head}</tr></thead>'
                f"<tbody>{body}</tbody></table>")

    if groups:
        sections = "".join(
            f"<h3>{g[0]}</h3>" + table_html(g[1], g[2], f"t{i}")
            for i, g in enumerate(groups))
    else:
        sections = table_html(headers, rows, "t0")
    qesc = urllib.parse.quote(str(q))
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>BCC 检索结果 · {qesc}</title><style>
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:24px;background:#fafafa}}
h1{{font-size:20px}} .meta{{color:#666;font-size:13px;margin-bottom:12px}}
input#flt{{padding:8px 12px;width:320px;border:1px solid #ccc;border-radius:6px;font-size:14px}}
table{{border-collapse:collapse;background:#fff;margin-top:12px;font-size:14px;max-width:1200px}}
th,td{{border:1px solid #ddd;padding:6px 10px;text-align:left}}
th{{background:#f0f4f8;cursor:pointer;white-space:nowrap}}
td:first-child{{color:#999}} .kw{{color:#c0392b;font-weight:600}}
tr:hover{{background:#f6f8ff}} .cnt{{color:#2c7be5}}
</style></head><body>
<h1>📚 BCC 检索结果</h1>
<div class="meta">检索式 <b>{q}</b> · 命中 <b class="cnt">{total}</b> ·
{time.strftime('%Y-%m-%d %H:%M')} · 师门 BCC 演讲口传语料(jieba 标注)</div>
<input id="flt" placeholder="🔍 在结果里筛选(如输入某词)…" onkeyup="fltAll()">
{sections}
<script>
function fltAll(){{var q=document.getElementById('flt').value.toLowerCase();
document.querySelectorAll('tbody').forEach(function(tb){{var n=0;
tb.querySelectorAll('tr').forEach(function(tr){{var hit=!q||tr.innerText.toLowerCase().indexOf(q)>=0;
tr.style.display=hit?'':'none';if(hit)n++;}});
tb.parentNode.setAttribute('data-shown',n);}});}}
function sortT(tid,col){{var tb=document.getElementById(tid).tBodies[0];
var rs=[].slice.call(tb.rows);var asc=tb.getAttribute('data-asc')!=col;
rs.sort(function(a,b){{var x=a.cells[col].innerText,y=b.cells[col].innerText;
var nx=parseFloat(x),ny=parseFloat(y);
if(!isNaN(nx)&&!isNaN(ny))return asc?nx-ny:ny-nx;
return asc?x.localeCompare(y,'zh'):y.localeCompare(x,'zh');}});
if(!asc)rs.reverse();tb.setAttribute('data-asc',asc?col:'-'+col);
rs.forEach(function(r){{tb.appendChild(r);}});}}
</script></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def _export_csv(out, path):
    headers, rows, groups = _rows_of(out)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if groups:
            for title, hs, rs in groups:
                w.writerow([title])
                w.writerow([h[1] for h in hs])
                w.writerows(rs)
                w.writerow([])
        else:
            w.writerow([h[1] for h in headers])
            w.writerows(rows)


def do_export(fmt, out, explicit_path):
    ext = {"xlsx": ".xlsx", "html": ".html", "csv": ".csv"}[fmt]
    stem = "".join(c if c.isalnum() or "\u4e00" <= c <= "\u9fff" else "_"
                   for c in str(out.get("query") or out.get("type")))[:40]
    fname = f"{time.strftime('%Y%m%d-%H%M%S')}-{stem}{ext}"
    if explicit_path:
        path = explicit_path
    else:
        base = _export_dir()
        if not base:
            return None  # 未配置存储目录:由调用方引导,不擅自落盘
        path = os.path.join(base, fname)
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    {"xlsx": _export_xlsx, "html": _export_html, "csv": _export_csv}[fmt](out, path)
    return path


def main():
    # 全局选项通过 parent parser 下发,保证 --corpus 等放在子命令前后都能识别;
    # default 用 SUPPRESS,避免子 parser 的默认值覆盖主 parser 已解析的值。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=argparse.SUPPRESS, help="语料目录")
    common.add_argument("--wordlist", action="append", default=argparse.SUPPRESS,
                        metavar="NAME=词1 词2", help="预定义词表,可多次")
    common.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS,
                        help="美化输出")
    common.add_argument("--export", choices=["html", "xlsx", "csv"],
                        nargs="?", const="html", default=argparse.SUPPRESS,
                        metavar="FMT",
                        help="导出全量结果文件;不带值默认 html(交互式,可搜索/排序)")
    common.add_argument("--out", default=argparse.SUPPRESS, metavar="PATH",
                        help="导出文件路径(默认桌面 bcc-results/)")

    ap = argparse.ArgumentParser(description="BCC 语料库检索 CLI",
                                 parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("freq", help="频率检索", parents=[common])
    p.add_argument("query")
    p.add_argument("--number", type=int, default=None)
    p.add_argument("--top", type=int, default=FREQ_TOP_DEFAULT)

    p = sub.add_parser("context", help="语境 KWIC 检索", parents=[common])
    p.add_argument("query")
    p.add_argument("--number", type=int, default=None)
    p.add_argument("--win-size", type=int, default=20)

    p = sub.add_parser("count", help="计数", parents=[common])
    p.add_argument("query")

    p = sub.add_parser("compare", help="对比两条检索式(频率+计数)", parents=[common])
    p.add_argument("query_a")
    p.add_argument("query_b")
    p.add_argument("--number", type=int, default=None)
    p.add_argument("--top", type=int, default=20)

    args = ap.parse_args()
    export = getattr(args, "export", None)
    # 导出模式默认拉全量(受 EXPORT_NUMBER 安全阀保护)
    full_default = EXPORT_NUMBER if export else 500
    if args.cmd == "freq":
        args.number = args.number if args.number is not None else 500
        if export:
            args.top = args.number
    elif args.cmd == "context":
        args.number = (args.number if args.number is not None
                       else (EXPORT_NUMBER if export else CONTEXT_NUMBER_DEFAULT))
    elif args.cmd == "compare":
        args.number = args.number if args.number is not None else full_default

    corpus_arg = getattr(args, "corpus", None)
    corpus = find_corpus(corpus_arg)
    if not corpus:
        if corpus_arg:
            err(f"指定的语料目录无效: {corpus_arg}",
                "目录需存在且包含 .txt 语料文件。不会自动改用其他语料库。")
        err("未找到语料目录",
            "请用 --corpus 指定包含 .txt 语料的目录,或让用户先运行 setup.py 导入语料。")

    t0 = time.time()
    try:
        wordlists = parse_wordlists(getattr(args, "wordlist", None))
    except ValueError as e:
        err(str(e), '用法: --wordlist "name=词1 词2"(等号分隔,空格分词),如 '
                    '"freq_adv=经常 常常 偶尔"')
    try:
        eng = make_engine(corpus)
        for name, words in wordlists.items():
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

    if export:
        try:
            exp_path = do_export(export, out, getattr(args, "out", None))
        except Exception as e:  # noqa: BLE001
            exp_path = None
            out["export_hint"] = f"导出失败: {e}(xlsx 需 openpyxl;html/csv 无依赖)"
        if exp_path:
            out["export_path"] = exp_path
            out["export_note"] = f"全量结果已导出: {exp_path}"
        elif "export_hint" not in out:
            out["export_hint"] = ("尚未配置存储目录。请询问用户想把检索结果存在哪个文件夹,"
                                  "然后运行 python scripts/config.py --results-dir <路径> 保存;"
                                  "或本次用 --out 指定完整文件路径。")

    print(json.dumps(out, ensure_ascii=False,
                     indent=2 if getattr(args, "pretty", False) else None))


if __name__ == "__main__":
    main()
