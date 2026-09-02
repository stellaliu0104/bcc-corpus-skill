# -*- coding: utf-8 -*-
"""语料预处理管线。

把各种来源的语料(.doc/.docx/.txt/.md/.xlsx)统一处理成 BCC 引擎能索引的格式:

    词/词性 词/词性 ... 。/w      (每行一句,GBK 编码)

流程:原始文件 → 纯文本 → 分句 → jieba 词性标注 → GBK 落盘

⚠️ 编码:BCC 的 DLL 内部用 GBK。语料必须以 GBK 落盘,配合 bcc_engine 的编码 patch
才能在 macOS 上正确检索中文词形(否则词形全部乱码)。详见 CLAUDE.md。
"""

import os
import re
import subprocess
import platform

import jieba.posseg as pseg


# ── 1. 各种格式 → 纯文本 ────────────────────────────────────────────────

def doc_to_text(path):
    """.doc / .docx → 纯文本字符串。

    macOS 用系统自带 textutil(无需额外依赖);其它平台尝试 python-docx(仅 .docx)。
    """
    ext = os.path.splitext(path)[1].lower()
    if platform.system() == "Darwin":
        # textutil 支持 .doc 和 .docx,转成 txt 输出到 stdout
        try:
            out = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", path],
                capture_output=True, check=True,
            )
            # textutil 输出通常是 UTF-8
            return out.stdout.decode("utf-8", errors="ignore")
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    # 跨平台 fallback:仅 .docx
    if ext == ".docx":
        try:
            from docx import Document  # python-docx,可选依赖
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise RuntimeError(
                "非 macOS 环境处理 .docx 需要 python-docx:pip install python-docx;"
                ".doc(旧格式)请先转成 .docx 或纯文本"
            )
    raise RuntimeError(f"无法转换 {path}:非 macOS 且不是 .docx")


def read_text_file(path):
    """读取纯文本 / markdown 文件,自动探测编码。"""
    import chardet
    with open(path, "rb") as f:
        raw = f.read()
    enc = chardet.detect(raw[:10240]).get("encoding") or "utf-8"
    return raw.decode(enc, errors="ignore")


def read_table_sentences(path, column=None):
    """从 Excel / Markdown 表格里抽取句子列。

    - .xlsx:读所有单元格中较长的文本;指定 column(表头列名)时只读该列
    - .md:抽取表格行里的中文长文本
    返回句子列表。
    """
    ext = os.path.splitext(path)[1].lower()
    sents = []
    if ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            col_idx = None
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    header = [str(c) if c is not None else "" for c in row]
                    if column:
                        col_idx = header.index(column) if column in header else None
                        if col_idx is not None:
                            continue  # 表头行本身不作为语料
                if col_idx is not None:
                    cell = row[col_idx] if col_idx < len(row) else None
                    cells = [cell]
                else:
                    cells = row
                for cell in cells:
                    if isinstance(cell, str) and len(cell.strip()) >= 4:
                        sents.append(cell.strip())
    elif ext == ".md":
        text = read_text_file(path)
        for line in text.splitlines():
            if "|" in line:  # 表格行
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
    """按中文句末标点切分成句子。"""
    sents = []
    for para in text.splitlines():
        para = para.strip()
        if not para:
            continue
        for s in _SENT_END.split(para):
            s = s.strip()
            if s and re.search(r"[一-鿿]", s):  # 至少含一个汉字
                sents.append(s)
    return sents


# ── 3. jieba 词性标注 → BCC 格式 ──────────────────────────────────────

def tag_sentence(sent):
    """一句话 → 'word/pos word/pos ...' 的 BCC 标注格式。"""
    parts = []
    for word, flag in pseg.cut(sent):
        word = word.strip()
        if not word:
            continue
        # BCC 用单字母词性(n/v/a/d...),jieba 的 flag 多为小写,直接沿用
        parts.append(f"{word}/{flag}")
    return " ".join(parts)


def annotate(sentences):
    """句子列表 → 标注句列表,并返回 (标注句, 原句) 映射。"""
    tagged, mapping = [], []
    for s in sentences:
        t = tag_sentence(s)
        if t:
            tagged.append(t)
            mapping.append((t, s))
    return tagged, mapping


# ── 4. GBK 落盘 ──────────────────────────────────────────────────────

def write_corpus(tagged, out_path):
    """标注句列表 → GBK 编码语料文件(每行一句)。

    先把每行 encode('gbk', errors='ignore') 再 decode 回来，
    强制滤掉 Mac GBK codec 允许但 Windows 不认的非法字节(如 0x80)。
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
    """把 '标注句 ↔ 原句' 映射写成 UTF-8 的 tsv,便于结果回显原文。"""
    os.makedirs(os.path.dirname(os.path.abspath(map_path)), exist_ok=True)
    with open(map_path, "w", encoding="utf-8") as f:
        for tagged, orig in mapping:
            f.write(f"{tagged}\t{orig}\n")


# ── 5. 一站式入口 ────────────────────────────────────────────────────

def process_file(in_path, out_dir, table_column=None, map_dir=None):
    """把单个输入文件处理成 BCC 语料,写入 out_dir。

    map_dir:原句↔标注句映射的存放目录。默认放到 out_dir 的同级 `_maps/`,
    ⚠️ 绝不能放进 out_dir(语料目录)——BCC 会索引该目录下所有文件,映射文件会污染索引。

    返回 dict:{name, sentences, out_path}
    """
    ext = os.path.splitext(in_path)[1].lower()
    if ext in (".doc", ".docx"):
        text = doc_to_text(in_path)
        sents = split_sentences(text)
    elif ext in (".xlsx", ".xls", ".md"):
        sents = read_table_sentences(in_path, column=table_column)
    else:  # .txt 及其它纯文本
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
        print("用法: python preprocess.py <输入文件> <输出目录>")
        sys.exit(1)
    info = process_file(sys.argv[1], sys.argv[2])
    print(f"✅ {info['name']}: {info['sentences']} 句 → {info['out_path']}")
