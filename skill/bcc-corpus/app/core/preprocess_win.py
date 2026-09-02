# -*- coding: utf-8 -*-
"""语料预处理管线 —— Windows 版。

与 Mac 版的唯一差异是 doc_to_text():
  - Windows: 用 pywin32 调用 Word/WPS COM 接口，支持 .doc 和 .docx
  - fallback: python-docx（仅 .docx）
  - GBK 写入做双向 encode/decode 过滤，保证 Windows GBK codec 能正常读取
"""

import os
import re
import tempfile

import jieba.posseg as pseg


# ── 1. 各种格式 → 纯文本 ─────────────────────────────────────────────

def doc_to_text(path):
    """.doc / .docx → 纯文本字符串（Windows）。

    优先用 pywin32 调 Word/WPS COM（支持 .doc 和 .docx）；
    COM 不可用时 fallback 到 python-docx（仅 .docx）。
    """
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()

    # ── 方案 A：pywin32 COM（支持 .doc 和 .docx）
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(path, ReadOnly=True)
            text = doc.Content.Text
            doc.Close(False)
        finally:
            word.Quit()
            pythoncom.CoUninitialize()
        return text
    except Exception:
        pass

    # ── 方案 B：python-docx（仅 .docx）
    if ext == ".docx":
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            pass

    raise RuntimeError(
        f"无法读取 {os.path.basename(path)}：\n"
        f".doc 文件需要安装 Microsoft Word 或 WPS Office，\n"
        f".docx 文件需要 python-docx（pip install python-docx）"
    )


def read_text_file(path):
    """读取纯文本文件，自动探测编码。"""
    import chardet
    with open(path, "rb") as f:
        raw = f.read()
    enc = chardet.detect(raw[:10240]).get("encoding") or "utf-8"
    return raw.decode(enc, errors="ignore")


def read_table_sentences(path, column=None):
    """从 Excel / Markdown 表格里抽取句子。"""
    ext = os.path.splitext(path)[1].lower()
    sents = []
    if ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                for cell in row:
                    if isinstance(cell, str) and len(cell.strip()) >= 4:
                        sents.append(cell.strip())
    elif ext == ".md":
        text = read_text_file(path)
        for line in text.splitlines():
            if "|" in line:
                for cell in line.split("|"):
                    cell = re.sub(r"[*`\[\]]", "", cell).strip()
                    if len(cell) >= 4 and re.search(r"[一-鿿]", cell):
                        sents.append(cell)
            elif len(line.strip()) >= 4 and re.search(r"[一-鿿]", line):
                sents.append(line.strip())
    return sents


# ── 2. 分句 ──────────────────────────────────────────────────────────

_SENT_END = re.compile(r"(?<=[。！？!?])")


def split_sentences(text):
    sents = []
    for para in text.splitlines():
        para = para.strip()
        if not para:
            continue
        for s in _SENT_END.split(para):
            s = s.strip()
            if s and re.search(r"[一-鿿]", s):
                sents.append(s)
    return sents


# ── 3. jieba 词性标注 → BCC 格式 ──────────────────────────────────────

def tag_sentence(sent):
    parts = []
    for word, flag in pseg.cut(sent):
        word = word.strip()
        if not word:
            continue
        parts.append(f"{word}/{flag}")
    return " ".join(parts)


def annotate(sentences):
    tagged, mapping = [], []
    for s in sentences:
        t = tag_sentence(s)
        if t:
            tagged.append(t)
            mapping.append((t, s))
    return tagged, mapping


# ── 4. GBK 落盘（Windows 安全版）───────────────────────────────────────

def write_corpus(tagged, out_path):
    """标注句列表 → GBK 编码语料文件。

    encode→decode 双向过滤，确保每个字节都是 Windows GBK 合法序列，
    避免 Mac GBK codec 写出的 0x80 等字节导致 Windows 解码失败。
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    cleaned = [
        line.encode("gbk", errors="ignore").decode("gbk", errors="ignore")
        for line in tagged
    ]
    with open(out_path, "w", encoding="gbk", errors="ignore") as f:
        f.write("\n".join(cleaned) + "\n")
    return len(cleaned)


def write_mapping(mapping, map_path):
    os.makedirs(os.path.dirname(os.path.abspath(map_path)), exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        for tagged, orig in mapping:
            f.write(f"{tagged}\t{orig}\n")


# ── 5. 一站式入口 ────────────────────────────────────────────────────

def process_file(in_path, out_dir, table_column=None, map_dir=None):
    ext = os.path.splitext(in_path)[1].lower()
    if ext in (".doc", ".docx"):
        text = doc_to_text(in_path)
        sents = split_sentences(text)
    elif ext in (".xlsx", ".xls", ".md"):
        sents = read_table_sentences(in_path, column=table_column)
    else:
        text = read_text_file(in_path)
        sents = split_sentences(text)

    tagged, mapping = annotate(sents)
    base = os.path.splitext(os.path.basename(in_path))[0]
    out_path = os.path.join(out_dir, base + ".txt")
    n = write_corpus(tagged, out_path)

    if map_dir is None:
        map_dir = os.path.join(os.path.dirname(os.path.abspath(out_dir)), "_maps")
    write_mapping(mapping, os.path.join(map_dir, base + ".map.tsv"))
    return {"name": base, "sentences": n, "out_path": out_path}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python preprocess_win.py <input_file> <output_dir>")
        sys.exit(1)
    info = process_file(sys.argv[1], sys.argv[2])
    print(f"OK {info['name']}: {info['sentences']} sentences -> {info['out_path']}")
