# -*- coding: utf-8 -*-
"""BCC 检索引擎封装。

在 LangSC.BCC 之上提供稳定、好用的检索函数,同时:
1. 打上 macOS GBK 编码 patch(见下),否则中文词形检索全部乱码/为 0;
2. 把 Run() 返回的 JSON 字符串解析成 Python dict,方便界面与 AI 使用;
3. 这几个函数也是阶段二喂给 AI(tool-use)的工具集。

用法:
    eng = BCCEngine("data/Corpus")
    eng.search_freq("a的n")         # 频率
    eng.search_context("很d")       # 上下文 KWIC
    eng.count("把n*v")              # 计数
    eng.define_wordlist("freq_adv", "经常 常常 偶尔")
"""

import os
import re
import json


# ── macOS GBK 编码 patch ─────────────────────────────────────────────
# LangSC 的 DLL 内部按 GBK 编码读写语料。但 _utils.detect_file_encoding 用 chardet
# 会把 GBK 中文文件识别成大写 "GB18030",而 file2corpus 只在编码恰好等于小写 "gbk"
# 时才把文件原样交给 DLL;否则走 UTF-8 转换临时文件 → DLL 按 GBK 读 → 中文乱码。
# 因此在导入 LangSC 前,把 detect_file_encoding 归一化:凡 GB 系编码一律返回 "gbk"。
def _install_gbk_patch():
    import LangSC._utils as U
    if getattr(U, "_gbk_patched", False):
        return
    _orig = U.detect_file_encoding

    def _patched(file_path, sample_size=1024 * 10):
        enc = _orig(file_path, sample_size)
        if enc and enc.lower() in ("gb18030", "gb2312", "gbk"):
            return "gbk"
        return enc

    U.detect_file_encoding = _patched
    U._gbk_patched = True


_install_gbk_patch()
from LangSC import BCC  # noqa: E402  (must import after patch)


class BCCEngine:
    """对 LangSC.BCC 的薄封装,返回解析好的 dict。"""

    def __init__(self, corpus_path="data/Corpus"):
        self.corpus_path = corpus_path
        self._bcc = None

    # 延迟初始化:第一次检索时才建/加载索引(建索引可能耗时)
    @property
    def bcc(self):
        if self._bcc is None:
            self._bcc = BCC(self.corpus_path)
        return self._bcc

    def reload(self):
        """语料/索引变更后强制重新加载。"""
        self._bcc = None
        return self.bcc

    @staticmethod
    def _parse(ret):
        """Run() 的返回统一解析成 dict;解析失败则包成 {'raw': ...}。"""
        if isinstance(ret, dict):
            return ret
        try:
            return json.loads(ret)
        except (json.JSONDecodeError, TypeError):
            return {"raw": ret}

    # ── 检索(也是 AI 的工具集)────────────────────────────────────────

    def search_freq(self, query, number=500, target="$Q"):
        """频率检索。返回 {type, query, total, distinct, records:[{word,freq}...]}。"""
        return self._parse(
            self.bcc.Run(query, Command="Freq", Number=number, Target=target)
        )

    def search_context(self, query, number=100, win_size=20, page_no=0):
        """上下文检索(KWIC)。records:[{keyword,left,right,doc}...]。

        注:LangSC 2.0.14 的 normalizer 期望 Context 项为 dict,但当前 DLL 返回的
        Context 是字符串数组(如 "...<Q>很耐心</Q>..."),导致 normalize 后 records 为空。
        这里绕过 normalizer,直接构造查询、解析原始 DLL 输出,自行拆分 KWIC。
        """
        # 复刻 LangSC 的查询构造逻辑,拿到原始检索式
        param = []
        self.bcc.GetBCCQueryInfo(
            {"Command": "Context", "Number": number,
             "WinSize": win_size, "PageNo": page_no},
            query, param,
        )
        raw = self.bcc.CallBCC(param[0])
        obj = self._parse(raw)
        records = []
        for i, item in enumerate(obj.get("Context", []) or [], 1):
            if isinstance(item, str):
                left, keyword, right = self._split_kwic(item)
                records.append({"id": i, "keyword": keyword,
                                "left": left, "right": right})
            elif isinstance(item, dict):
                left, keyword, right = self._split_kwic(item.get("Context", ""))
                records.append({"id": i, "keyword": keyword, "left": left,
                                "right": right,
                                "doc": (item.get("Source", "") or "")})
        return {
            "type": "Context",
            "query": query,
            "total": obj.get("Total", len(records)),
            "approximate": obj.get("Approximate") == "1",
            "records": records,
        }

    @staticmethod
    def _split_kwic(ctx):
        """'前<Q>关键词</Q>后' → (left, keyword, right)。"""
        m = re.search(r"<Q>(.*?)</Q>", ctx)
        if m:
            return ctx[:m.start()], m.group(1), ctx[m.end():]
        return ctx, "", ""

    def count(self, query):
        """计数检索。返回 {type, query, total, ...}。"""
        return self._parse(self.bcc.Run(query, Command="Count"))

    def define_wordlist(self, name, words):
        """定义检索词表(供 {$1=[name]} 引用)。words 为空格/逗号分隔的字符串。"""
        return self.bcc.AddBCCKV(name, words)

    def get_wordlist(self, name=""):
        return self._parse(self.bcc.GetBCCKV(name))

    def clear_wordlist(self, name=""):
        return self.bcc.ClearBCCKV(name)

    def raw_query(self, query):
        """执行原始 BCC 检索式(高级用法,含 AND/NOT/自定义操作)。"""
        return self._parse(self.bcc.Run(query))


# ── AI tool-use 的工具描述(阶段二会用到,阶段一先备着)───────────────
TOOL_SPECS = [
    {
        "name": "search_freq",
        "description": "对语料库做频率检索,统计某检索式命中的词/结构的频率分布。"
                       "适合回答『X 有多少种搭配』『哪个最高频』。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "BCC 检索式,如 a的n、很(~){$1=[freq_adv]}"},
                "number": {"type": "integer", "description": "返回条数上限,默认 500"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_context",
        "description": "对语料库做上下文检索(KWIC),返回检索式命中的真实语境例句。"
                       "适合『给我看用例』『在什么语境下出现』。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "BCC 检索式"},
                "number": {"type": "integer", "description": "返回例句数上限,默认 100"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "count",
        "description": "只返回某检索式在语料库中的命中总数。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "BCC 检索式"}},
            "required": ["query"],
        },
    },
]


if __name__ == "__main__":
    eng = BCCEngine("data/Corpus")
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "a的n"
    print(json.dumps(eng.search_freq(q), ensure_ascii=False, indent=2))
