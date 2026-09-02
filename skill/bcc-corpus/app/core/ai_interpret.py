# -*- coding: utf-8 -*-
"""层次 B:让 AI 解读 BCC 返回的频率表 / KWIC 语境。"""

import json


SYSTEM = """你是汉语语言学研究助手。用户在语料库里跑了一条检索,拿到了频率数据或语境例句。\
请你作为语言学研究者解读这些结果,帮助用户发现规律。

要求:
1. 先用一两句话概括检索结果的总体情况(命中量、最突出的现象)。
2. 分点给出观察到的规律:如高频搭配、句法分布、语义倾向、异常或值得注意的现象。
3. 如果数据支持分类(如按句法功能:定语/状语/谓语),给出分类归纳。
4. 指出存疑点或需要进一步检索验证的地方。
5. 用中文,条理清晰,像写研究笔记。不要编造数据里没有的内容。"""


COMPARE_SYSTEM = """你是汉语语言学研究助手。用户对两个语言形式分别做了语料库检索,\
现在需要你对比分析两组结果,揭示它们的差异与规律。

要求:
1. 先概述两组数据的总体情况(命中量、分布概貌)。
2. 从以下维度逐一对比(有数据支持的才写):
   - 频率/数量差异
   - 高频搭配/共现词的异同
   - 句法分布差异(如前置成分、后接成分)
   - 语义/语用倾向差异
3. 归纳核心区别,用 1~2 句话概括两者最本质的不同。
4. 指出数据局限或需要进一步验证的问题。
5. 用中文,条理清晰,像写研究笔记。不要编造数据里没有的内容。"""


def _format_result(result):
    """把检索结果 dict 压缩成喂给 AI 的紧凑文本。"""
    typ = result.get("type", "")
    query = result.get("query", "")
    total = result.get("total", 0)
    lines = [f"检索式: {query}", f"类型: {typ}", f"命中总量: {total}"]
    records = result.get("records", [])
    if typ == "Freq":
        lines.append(f"不同词数: {result.get('distinct', len(records))}")
        lines.append("频率分布(词: 频次):")
        for r in records[:100]:
            lines.append(f"  {r.get('word', '')}: {r.get('freq', 0)}")
    elif typ == "Context":
        lines.append("语境例句(左 [关键词] 右):")
        for r in records[:60]:
            lines.append(f"  {r.get('left', '')}[{r.get('keyword', '')}]{r.get('right', '')}")
    return "\n".join(lines)


def interpret(result, llm, question=""):
    """解读单条检索结果,返回分析文字。"""
    payload = _format_result(result)
    user = payload
    if question:
        user = f"用户的研究问题:{question}\n\n检索结果:\n{payload}"
    return llm.chat(system=SYSTEM, user=user, max_tokens=1500, temperature=0.3)


def compare_interpret(result_a, result_b, llm, question="", label_a="A", label_b="B"):
    """对比解读两条检索结果,返回对比分析文字。"""
    block_a = f"【{label_a}】\n{_format_result(result_a)}"
    block_b = f"【{label_b}】\n{_format_result(result_b)}"
    user = f"{block_a}\n\n{block_b}"
    if question:
        user = f"用户的研究问题:{question}\n\n{user}"
    return llm.chat(system=COMPARE_SYSTEM, user=user, max_tokens=2000, temperature=0.3)

