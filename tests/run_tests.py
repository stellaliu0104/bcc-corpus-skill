#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bcc-corpus-skill 自动化测试 runner(零第三方依赖)。

用法:
  python tests/run_tests.py                          # L1 引擎层全量
  python tests/run_tests.py --corpus /path/to/Corpus
  python tests/run_tests.py --suite translate        # L2 离线校验(测试集格式)
  python tests/run_tests.py --suite translate --llm  # L2 + 本地 LLM 预验证
                                                     #   需环境变量 LLM_BASE_URL/LLM_API_KEY/LLM_MODEL

退出码: 失败用例数(0 = 全绿)。
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEARCH = os.path.join(HERE, "..", "skill", "bcc-corpus", "scripts", "search.py")


def load(suite):
    with open(os.path.join(HERE, f"testset_{suite}.json"), encoding="utf-8") as f:
        return json.load(f)["cases"]


def run_cli(args, timeout=180):
    """跑 search.py 子进程,返回 (exit_code, parsed_json_or_None, raw_stdout)。"""
    proc = subprocess.run(
        [sys.executable, SEARCH] + args,
        capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout.strip()
    parsed = None
    if out:
        try:
            parsed = json.loads(out.splitlines()[-1])
        except json.JSONDecodeError:
            parsed = None
    return proc.returncode, parsed, out


def check_engine_case(case):
    """返回 (pass: bool, detail: str)。"""
    exp = case["expect"]
    code, data, raw = run_cli(case["args"])

    if exp.get("json_valid") or "ok" in exp or "ok_in" in exp:
        if data is None:
            return False, f"输出不是合法 JSON: {raw[:200]!r}"
    if "ok" in exp and (data or {}).get("ok") != exp["ok"]:
        return False, f"ok 期望 {exp['ok']},实际 {((data or {}).get('ok'))}"
    if "ok_in" in exp and (data or {}).get("ok") not in exp["ok_in"]:
        return False, f"ok 不在允许集合 {exp['ok_in']}"
    if data is None:
        return True, "json_valid-only case"

    for key in ("type",):
        if key in exp and data.get(key) != exp[key]:
            return False, f"type 期望 {exp[key]},实际 {data.get(key)}"

    total = data.get("total")
    if "min_total" in exp:
        if not isinstance(total, (int, float)) or total < exp["min_total"]:
            # compare 子命令没有顶层 total,检查 items
            items = data.get("items") or []
            if not items or not all(
                isinstance(i.get("count_total"), (int, float)) for i in items
            ):
                return False, f"total={total!r} 低于阈值 {exp['min_total']}"

    records = data.get("records") or data.get("top") or []
    if "min_records" in exp and len(records) < exp["min_records"]:
        return False, f"records 数 {len(records)} < {exp['min_records']}"
    for key in exp.get("record_keys", []):
        if records and any(key not in r for r in records[:3]):
            return False, f"records 缺少字段 {key}"

    if "items_length" in exp and len(data.get("items") or []) != exp["items_length"]:
        return False, f"items 长度 {len(data.get('items') or [])} != {exp['items_length']}"
    for key in exp.get("item_keys", []):
        items = data.get("items") or []
        if items and any(key not in i for i in items):
            return False, f"items 缺少字段 {key}"

    return True, "ok"


# ── L2 翻译层 ────────────────────────────────────────────────────────

PROMPT_TMPL = """你是 BCC 语料库检索助手。用户用自然语言描述研究问题,你输出 BCC 检索式。

以下是 BCC 检索语法说明:

{syntax}

以下是"研究问题→检索式"对照示例库(优先照搬同型例子,替换词/词性):

{examples}

【重要规则】
1. 跨词通配用 `*`(任意词数、不跨标点),而非 `~`(恰好一个词)。
2. 问题涉及「A 与 B 的对比/差别/区别/比较/分工」时,输出三行:
   COMPARE
   [A] 检索式A
   [B] 检索式B
3. 单条查询只输出一行检索式本身——不要加 Freq()/Context() 等操作后缀,不要加解释。
4. 查"某类词"优先用词表条件,如 `很(~){{$1=[经常 常常 偶尔 时常 往往]}}`。
5. 词性 v 分不出心理动词等语义小类,此类需求用词表。

用户问题: {question}
你的输出:"""


def translate_with_llm(question, syntax, examples=""):
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    style = os.environ.get("LLM_API_STYLE", "openai")  # openai | anthropic
    if not (base and key and model):
        return None, "未配置 LLM_BASE_URL/LLM_API_KEY/LLM_MODEL"
    import urllib.request
    system = PROMPT_TMPL.format(syntax=syntax, examples=examples, question=question)
    # 思考型模型的 thinking 会消耗 token 预算,300 会导致正文为空
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "2000"))
    if style == "anthropic":
        req = urllib.request.Request(
            base + "/v1/messages",
            data=json.dumps({
                "model": model, "max_tokens": max_tokens, "temperature": 0.0,
                "system": system,
                "messages": [{"role": "user", "content": question}],
            }).encode(),
            headers={"Content-Type": "application/json",
                     "x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text").strip()
    else:
        req = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                "temperature": 0.0, "max_tokens": max_tokens,
            }).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"].strip()

    # 后处理:去掉模型擅自附加的操作后缀(如 "居然Context(10,1,50)" → "居然")
    import re as _re
    text = _re.sub(r"\s*(?:Freq|Context|Count)\([^)]*\)\s*$", "", text).strip()
    text = _re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines and lines[0].upper() == "COMPARE" and len(lines) >= 3:
        qs = [l.split("]", 1)[1].strip() if "]" in l else l for l in lines[1:3]]
        return {"mode": "compare", "queries": qs}, None
    return {"mode": "single", "query": lines[0].strip("` ") if lines else text}, None


def check_translate_case(case, syntax, examples, use_llm):
    if not use_llm:
        # 离线:只做测试集自检(字段齐全、must_not 不与 expected 冲突)
        exp = case.get("expected")
        if case["mode"] == "compare":
            ok = isinstance(exp, list) and len(exp) == 2
        else:
            ok = isinstance(exp, str) and bool(exp)
        if case.get("check") == "wordlist_superset":
            ok = bool(case.get("core_words"))
        return ok, "format-only" + ("" if ok else " (字段类型/内容错误)")

    got, err = translate_with_llm(case["question"], syntax, examples)
    if err:
        return False, err
    if got["mode"] != case["mode"]:
        return False, f"模式期望 {case['mode']},得到 {got['mode']}"

    if case.get("check") == "wordlist_superset":
        # 词表类:模型给出的词表是语义超集即可接受,核心词必须齐、结构必须对
        q = got["queries"][0] if got["mode"] == "compare" else got["query"]
        if "{$1=[" not in q:
            return False, f"缺少词表条件: {q!r}"
        wl = q.split("{$1=[", 1)[1].split("]", 1)[0].split()
        missing = [w for w in case["core_words"] if w not in wl]
        if missing:
            return False, f"词表缺核心词 {missing}: {q!r}"
        for bad in case.get("must_not", []):
            if bad in q:
                return False, f"命中禁止模式 {bad!r}"
        return True, q

    if case["mode"] == "compare":
        got_qs = got["queries"]
        exp_qs = case["expected"]
        ok = all(g.strip() == e.strip() for g, e in zip(got_qs, exp_qs))
        return ok, f"got={got_qs} exp={exp_qs}"
    q = got["query"]
    if q != case["expected"]:
        return False, f"got={q!r} exp={case['expected']!r}"
    for bad in case.get("must_not", []):
        if bad in q:
            return False, f"命中禁止模式 {bad!r}"
    return True, q


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["engine", "translate"], default="engine")
    ap.add_argument("--corpus", default=os.environ.get("BCC_CORPUS"))
    ap.add_argument("--llm", action="store_true", help="translate 套件启用本地 LLM 预验证")
    args = ap.parse_args()

    if args.corpus:
        os.environ["BCC_CORPUS"] = args.corpus

    cases = load(args.suite)
    syntax = ""
    examples = ""
    if args.suite == "translate":
        ref_dir = os.path.join(HERE, "..", "skill", "bcc-corpus", "references")
        with open(os.path.join(ref_dir, "bcc_syntax.md"), encoding="utf-8") as f:
            syntax = f.read()
        with open(os.path.join(ref_dir, "examples.md"), encoding="utf-8") as f:
            examples = f.read()

    print(f"== suite: {args.suite} | cases: {len(cases)} | llm: {args.llm} ==\n")
    fails = 0
    t0 = time.time()
    for c in cases:
        try:
            if args.suite == "engine":
                ok, detail = check_engine_case(c)
            else:
                ok, detail = check_translate_case(c, syntax, examples, args.llm)
        except subprocess.TimeoutExpired:
            ok, detail = False, "TIMEOUT"
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"runner 异常: {e}"
        mark = "PASS" if ok else "FAIL"
        if not ok:
            fails += 1
        print(f"[{mark}] {c['id']:<32} {detail}")

    dt = time.time() - t0
    print(f"\n== {len(cases) - fails}/{len(cases)} passed in {dt:.1f}s ==")
    sys.exit(min(fails, 1) if fails else 0)


if __name__ == "__main__":
    main()
