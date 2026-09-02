# -*- coding: utf-8 -*-
"""层次 A:把中文研究问题翻译成 BCC 检索式。

返回值:
  单条模式 → str
  对比模式 → {"mode": "compare", "labels": [str, str], "queries": [str, str]}
"""

import os
import re
import json


def _load_syntax():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "grammar", "bcc_syntax.md")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


SYSTEM_TEMPLATE = """你是 BCC 语料库检索助手。用户用自然语言描述研究问题,你输出 BCC 检索式。

本语料库用 jieba 分词和词性标注,常用词性:
n名词 v动词 a形容词 d副词 r代词 p介词 uj助词"的" m数词 q量词 w标点 ns地名 nr人名 \
vn动名词 ad副形词。

以下是 BCC 检索语法说明:

{syntax}

──────────────────────────────────────────────
【重要规则】

1. 跨词通配用 `*`(任意词数、不跨标点),而非 `~`(恰好一个词)。
   如 `如果*就` 而非 `如果~就`。

2. 如果用户问题涉及「A 与 B 的对比/差别/区别/比较」,必须输出【对比模式】,
   格式严格如下(三行,无多余文字):
   COMPARE
   [标签A] 检索式A
   [标签B] 检索式B

3. 如果是单条查询,只输出一行检索式,无前缀、无代码块、无解释。

4. 查"某类词"优先用词表条件,如 `很(~){{$1=[经常 常常 偶尔 时常 往往]}}`。

5. 词性 v 无法区分心理动词和情态动词,遇到此类需求用词表,如
   `太(~){{$1=[喜欢 担心 害怕 后悔 失望 高兴 悲伤 愤怒]}}`。
──────────────────────────────────────────────
"""


def translate(question, llm):
    """中文问题 → 单条检索式(str) 或对比结构(dict)。"""
    system = SYSTEM_TEMPLATE.format(syntax=_load_syntax())
    raw = llm.chat(system=system, user=question, max_tokens=300, temperature=0.0)

    raw = raw.strip()
    # 去代码块
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw).strip()

    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    # 对比模式检测
    if lines and lines[0].upper() == "COMPARE" and len(lines) >= 3:
        def _parse_labeled(line):
            m = re.match(r"\[(.+?)\]\s*(.+)", line)
            if m:
                return m.group(1).strip(), m.group(2).strip()
            return line, line

        label_a, query_a = _parse_labeled(lines[1])
        label_b, query_b = _parse_labeled(lines[2])
        return {"mode": "compare", "labels": [label_a, label_b],
                "queries": [query_a, query_b]}

    # 单条模式
    q = lines[0] if lines else raw
    return q.strip("`").strip()
