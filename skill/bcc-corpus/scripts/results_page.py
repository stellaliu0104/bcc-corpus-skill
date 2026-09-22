#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成、打开并清理 BCC 临时检索结果页。

页面为独立 file:// HTML，不依赖常驻 Streamlit 服务。它包含前端分页、筛选、排序
和浏览器下载导出。静态网页不能可靠得知标签页何时关闭，因此临时页面在下一次查询
创建前删除，并在 24 小时后过期删除；用户点击导出得到的下载文件不在清理范围内。
"""

import html
import json
import os
import re
import time
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
DEFAULT_RESULTS_DIR = os.path.join(SKILL_ROOT, "data", "results")
TEMP_PREFIX = "bcc-temporary-"
TEMP_TTL_SECONDS = 24 * 60 * 60
PAGE_SIZE = 50
POS_TAG = re.compile(r"/[A-Za-z]+")
SPACE = re.compile(r"\s+")


def cleanup_temp_pages(remove_all=False):
    """清理上一轮页面或超时页面；绝不触碰浏览器下载的用户导出文件。"""
    if not os.path.isdir(DEFAULT_RESULTS_DIR):
        return 0
    now = time.time()
    removed = 0
    for name in os.listdir(DEFAULT_RESULTS_DIR):
        if not name.startswith(TEMP_PREFIX) or not name.endswith(".html"):
            continue
        path = os.path.join(DEFAULT_RESULTS_DIR, name)
        try:
            if remove_all or now - os.path.getmtime(path) > TEMP_TTL_SECONDS:
                os.remove(path)
                removed += 1
        except OSError:
            pass
    return removed


def plain(text):
    """将 BCC 标注文本或 KWIC 文本归一为供匹配的纯文本。"""
    text = POS_TAG.sub("", text or "")
    return SPACE.sub("", text).replace("|", "")


def display_text(text):
    """把 BCC 标注行还原为紧凑中文展示文本。

    BCC 语料的每个分词之间有空格（如“他/r 居然/d 把/p”）。删掉词性
    标记后，这些空格不是原文的一部分，必须一并去除；竖线是旧语料的
    人工分隔符，同样不应在中文展示中留下空白。
    """
    text = POS_TAG.sub("", text or "").replace("|", "")
    return SPACE.sub("", text).strip()


def _lines_for_keyword(corpus, keyword, cache):
    key = plain(keyword)
    if key in cache:
        return cache[key]
    matches = []
    try:
        names = sorted(name for name in os.listdir(corpus) if name.endswith(".txt"))
    except OSError:
        return matches
    for name in names:
        path = os.path.join(corpus, name)
        try:
            with open(path, "r", encoding="gbk", errors="replace") as source:
                lines = [display_text(line) for line in source if line.strip()]
                for index, text in enumerate(lines):
                    normalized = plain(text)
                    if key and key in normalized:
                        # 发布语料已按句切分，原始段落边界不再保留；先保存整篇
                        # 连续文本，后续以命中词为中心截取前后各 200 个字符。
                        matches.append((name, index + 1, text, normalized, index, lines))
        except OSError:
            continue
    cache[key] = matches
    return matches


def _score(record, normalized_sentence):
    left = plain(record.get("left", ""))[-18:]
    keyword = plain(record.get("keyword", ""))
    right = plain(record.get("right", ""))[:18]
    score = 0
    if keyword and keyword in normalized_sentence:
        score += 5
    if left and left in normalized_sentence:
        score += len(left) * 3
    if right and right in normalized_sentence:
        score += len(right) * 3
    if left and left[-8:] in normalized_sentence:
        score += 4
    if right and right[:8] in normalized_sentence:
        score += 4
    return score


def add_provenance(records, corpus):
    """为 Context records 增加 source_document/source_line/sentence/source_status。"""
    cache = {}
    for record in records:
        if record.get("doc"):
            record["source_document"] = record["doc"]
            record["source_status"] = "引擎返回"
            continue
        candidates = _lines_for_keyword(corpus, record.get("keyword", ""), cache)
        if not candidates:
            record["source_status"] = "未定位"
            continue
        best = max(candidates, key=lambda item: _score(record, item[3]))
        if _score(record, best[3]) < 9:
            record["source_status"] = "未能可靠定位"
            continue
        record["source_document"] = best[0]
        record["source_line"] = best[1]
        record["sentence"] = best[2]
        all_text = "\n".join(best[5])
        sentence_start = sum(len(line) + 1 for line in best[5][:best[4]])
        keyword_pos = all_text.find(plain(record.get("keyword", "")), sentence_start)
        if keyword_pos < 0:
            keyword_pos = sentence_start
        key_len = max(1, len(plain(record.get("keyword", ""))))
        start, end = max(0, keyword_pos - 200), min(len(all_text), keyword_pos + key_len + 200)
        record["passage"] = (("…" if start else "") + all_text[start:end] +
                             ("…" if end < len(all_text) else ""))
        record["source_status"] = "原始语料回查"
    return records


def _highlight(text, keyword):
    escaped = html.escape(display_text(text))
    needle = html.escape(display_text(keyword))
    return escaped.replace(needle, f'<mark>{needle}</mark>') if needle else escaped


def _snippet(record, radius=25):
    """展示命中句所在语境中查询目标前后共约 50 个字符。"""
    sentence = display_text(record.get("sentence") or "")
    passage = display_text(record.get("passage") or "")
    keyword = display_text(record.get("keyword") or "")
    text = passage or sentence
    if not text or not keyword:
        return sentence or display_text(record.get("left", "")) + keyword + display_text(record.get("right", ""))
    index = text.find(keyword)
    if index < 0:
        return sentence or text
    start, end = max(0, index - radius), min(len(text), index + len(keyword) + radius)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def _context_table(records):
    rows = []
    for index, record in enumerate(records):
        source = record.get("source_document") or "未定位"
        if record.get("source_line"):
            source += f" · 第 {record['source_line']} 行"
        rows.append(f"""<tr>
<td>{record.get('id', '')}</td>
<td class="sentence">{_highlight(_snippet(record), record.get('keyword'))}</td>
<td><b>{html.escape(source)}</b><small>{html.escape(record.get('source_status', ''))}</small></td>
<td><button class="detail" onclick="showPassage({index})">查看完整段落</button></td>
</tr>""")
    return "".join(rows) or '<tr><td colspan="4">没有可展示的上下文结果。</td></tr>'


def _export_records(records):
    """只保留浏览器导出所需字段，避免把内部回查字段塞进页面。"""
    return [{
        "序号": r.get("id", ""),
        "关键词": display_text(r.get("keyword")),
        "左上下文": display_text(r.get("left")),
        "右上下文": display_text(r.get("right")),
        "命中句与上下文（约50字）": _snippet(r),
        "完整语境段落": display_text(r.get("passage")) or display_text(r.get("sentence")) or "—",
        "出处": (r.get("source_document") or "未定位") +
              (f" · 第 {r['source_line']} 行" if r.get("source_line") else ""),
        "出处状态": r.get("source_status", ""),
    } for r in records]


def write_page(query, records, total, corpus, command, truncated=False):
    """写出临时分页结果页并返回绝对路径。调用方先 cleanup_temp_pages。"""
    add_provenance(records, corpus)
    os.makedirs(DEFAULT_RESULTS_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() or "\u4e00" <= c <= "\u9fff" else "_" for c in query)[:40]
    path = os.path.join(DEFAULT_RESULTS_DIR, f"{TEMP_PREFIX}{time.strftime('%Y%m%d-%H%M%S')}-{safe or command}.html")
    note = (f"页面展示前 {len(records)} 条；总命中 {total} 条。" if truncated
            else f"已展示全部 {len(records)} 条命中。")
    data_json = json.dumps(_export_records(records), ensure_ascii=False).replace("</", "<\\/")
    html_doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>BCC 全部检索结果 · {html.escape(query)}</title>
<style>
:root{{color-scheme:light;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}body{{margin:0;background:#f5f7fb;color:#162033}}header{{padding:26px max(24px,calc((100vw - 1300px)/2));background:linear-gradient(120deg,#09203f,#335c9b);color:#fff}}h1{{margin:0 0 8px;font-size:25px}}.meta{{opacity:.9;font-size:14px}}main{{max-width:1300px;margin:20px auto;padding:0 20px}}.notice{{background:#eaf2ff;border-left:4px solid #3377d7;padding:12px 14px;border-radius:5px;margin:12px 0 16px}}.bar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}#filter{{width:min(440px,100%);padding:11px 13px;border:1px solid #b6c2d1;border-radius:8px;font-size:14px;background:#fff}}button{{border:1px solid #b6c2d1;background:#fff;border-radius:7px;padding:9px 11px;cursor:pointer;color:#203a5c;font-size:13px}}button:hover{{background:#eaf2ff}}button.detail{{white-space:nowrap;background:#f4f8ff}}.count{{margin:11px 0;color:#526071;font-size:13px}}.table-wrap{{background:#fff;border:1px solid #dce3ec;border-radius:9px;overflow:auto;box-shadow:0 1px 4px #18233d12}}table{{border-collapse:collapse;width:100%;min-width:820px;font-size:14px}}th{{position:sticky;top:0;background:#edf3fa;color:#263b55;text-align:left;padding:11px;border-bottom:1px solid #ccd7e3;cursor:pointer;white-space:nowrap}}td{{padding:11px;border-bottom:1px solid #e6ebf1;vertical-align:top;line-height:1.65}}tr:hover{{background:#f4f8ff}}td:first-child{{color:#718096;width:42px;text-align:right}}.sentence{{min-width:500px;max-width:720px}}mark{{background:#ffe083;color:#7d4200;padding:1px 2px;border-radius:2px;font-weight:700}}small{{display:block;color:#718096;margin-top:4px}}.pager{{display:flex;align-items:center;gap:8px;margin:14px 0 4px}}.pager button:disabled{{opacity:.45;cursor:not-allowed}}footer{{color:#788596;font-size:12px;padding:16px 0 30px}}dialog{{border:0;border-radius:12px;box-shadow:0 18px 60px #0005;width:min(780px,calc(100vw - 40px));padding:0}}dialog::backdrop{{background:#10233c99}}.dialog-head{{background:#edf3fa;padding:15px 18px;font-weight:700;display:flex;justify-content:space-between;align-items:center}}.dialog-body{{padding:18px;white-space:pre-wrap;line-height:1.9;max-height:65vh;overflow:auto}}.dialog-meta{{color:#62758a;font-size:13px;margin:0 0 12px}}.close{{font-size:18px;padding:3px 9px}}
</style></head><body><header><h1>📚 BCC 全部检索结果</h1><div class="meta">检索式：<b>{html.escape(query)}</b>　·　检索类型：{html.escape(command)}　·　命中：<b>{total}</b>　·　{time.strftime('%Y-%m-%d %H:%M')}</div></header>
<main><div class="notice">{html.escape(note)} 列表只展示命中句及查询目标前后共约 50 字；黄色高亮为查询目标。点击“查看完整段落”可展开以命中词为中心前后各最多 200 字的连续语境。出处由引擎返回或在本机原始语料中回查定位；“未定位”表示命中了检索式，但无法从 KWIC 可靠唯一回查到某个源文件。此页面为临时文件：下一次查询时或 24 小时后自动清理；点击导出下载的文件会保留。</div>
<div class="bar"><input id="filter" autofocus placeholder="🔍 筛选命中句或出处…" oninput="applyFilter()"><button onclick="exportCSV()">导出 CSV（Excel 可打开）</button><button onclick="exportHTML()">导出 HTML</button></div><div id="count" class="count"></div>
<div class="table-wrap"><table id="results"><thead><tr><th onclick="sortTable(0)"># ↕</th><th onclick="sortTable(1)">命中句与上下文（约 50 字）↕</th><th onclick="sortTable(2)">出处 ↕</th><th>详情</th></tr></thead><tbody>{_context_table(records)}</tbody></table></div><div class="pager"><button id="prev" onclick="go(-1)">← 上一页</button><span id="pageInfo"></span><button id="next" onclick="go(1)">下一页 →</button></div>
<footer>发布语料已按句切分，原始段落边界不再保留；完整语境以命中词为中心前后各最多 200 个连续字符展示。“未定位”表示该命中没有可可靠唯一确认的源文件，避免误标出处。</footer></main><dialog id="passageDialog"><div class="dialog-head"><span>完整语境段落</span><button class="close" onclick="passageDialog.close()">×</button></div><div class="dialog-body"><p id="dialogMeta" class="dialog-meta"></p><div id="dialogText"></div></div></dialog>
<script id="exportData" type="application/json">{data_json}</script><script>
const pageSize={PAGE_SIZE};let page=1,sortAsc=true;const rows=[...document.querySelectorAll('#results tbody tr')];const data=JSON.parse(document.getElementById('exportData').textContent);let filtered=rows;const passageDialog=document.getElementById('passageDialog');
function render(){{const pages=Math.max(1,Math.ceil(filtered.length/pageSize));page=Math.min(page,pages);rows.forEach(r=>r.style.display='none');filtered.slice((page-1)*pageSize,page*pageSize).forEach(r=>r.style.display='');document.getElementById('count').textContent=`筛选后 ${{filtered.length}} 条 · 每页 ${{pageSize}} 条`;document.getElementById('pageInfo').textContent=`第 ${{page}} / ${{pages}} 页`;document.getElementById('prev').disabled=page<=1;document.getElementById('next').disabled=page>=pages;}}
function applyFilter(){{const q=document.getElementById('filter').value.toLowerCase();filtered=rows.filter(r=>!q||r.innerText.toLowerCase().includes(q));page=1;render();}}
function go(n){{page+=n;render();}}
function sortTable(c){{rows.sort((a,b)=>{{const x=a.cells[c].innerText,y=b.cells[c].innerText;if(c===0)return sortAsc?(+x)-(+y):(+y)-(+x);return sortAsc?x.localeCompare(y,'zh'):y.localeCompare(x,'zh')}});sortAsc=!sortAsc;const body=document.querySelector('#results tbody');rows.forEach(r=>body.appendChild(r));applyFilter();}}
function activeData(){{const q=document.getElementById('filter').value.toLowerCase();return data.filter(x=>!q||Object.values(x).join(' ').toLowerCase().includes(q));}}
function download(name,type,content){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{{type}}));a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{{URL.revokeObjectURL(a.href);a.remove()}},1000);}}
function stamp(){{return new Date().toISOString().slice(0,19).replace(/[:T]/g,'-');}}
function showPassage(index){{const item=data[index];document.getElementById('dialogMeta').textContent=`${{item['出处']}} · ${{item['出处状态']}}`;const keyword=item['关键词'];const parts=esc(item['完整语境段落']).split(esc(keyword));document.getElementById('dialogText').innerHTML=parts.join('<mark>'+esc(keyword)+'</mark>');passageDialog.showModal();}}
function csvCell(v){{return '"'+String(v??'').replaceAll('"','""')+'"';}}
function exportCSV(){{const items=activeData(),heads=['序号','关键词','命中句与上下文（约50字）','完整语境段落','出处','出处状态'];const csv='\\uFEFF'+[heads,...items.map(x=>heads.map(h=>x[h]))].map(r=>r.map(csvCell).join(',')).join('\\r\\n');download(`BCC检索结果-${{stamp()}}.csv`,'text/csv;charset=utf-8',csv);}}
function esc(v){{return String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');}}
function exportHTML(){{const items=activeData(),heads=['序号','关键词','命中句与上下文（约50字）','完整语境段落','出处','出处状态'];const body=items.map(x=>'<tr>'+heads.map(h=>'<td>'+esc(x[h])+'</td>').join('')+'</tr>').join('');const doc='<!doctype html><meta charset="utf-8"><title>BCC 检索结果</title><style>body{{font-family:system-ui,"PingFang SC";margin:24px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccc;padding:7px;text-align:left;vertical-align:top}}th{{background:#eef3f8}}</style><h1>BCC 检索结果</h1><p>检索式：'+esc({json.dumps(query, ensure_ascii=False)})+'；导出条数：'+items.length+'</p><table><tr>'+heads.map(h=>'<th>'+h+'</th>').join('')+'</tr>'+body+'</table>';download(`BCC检索结果-${{stamp()}}.html`,'text/html;charset=utf-8',doc);}}
render();
</script></body></html>"""
    with open(path, "w", encoding="utf-8") as out:
        out.write(html_doc)
    return path


def open_page(path):
    try:
        return bool(webbrowser.open("file://" + urllib.parse.quote(path)))
    except Exception:  # noqa: BLE001
        return False
