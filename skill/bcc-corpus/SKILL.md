---
name: bcc-corpus
description: BCC 语料库检索技能。当用户提出语料检索、词汇/句式搭配统计、频率对比、查真实例句、导入新语料、删除语料、打开语料库界面等需求时使用。触发词：语料、语料库、BCC、检索、搭配、频率、例句、用例、对比、副词、代词、导入语料、删除语料、移除语料、完整界面。
---

# BCC 语料库检索技能

帮用户在师门 BCC 语料库（演讲/口传语料）上做语言学检索与统计。你负责：把用户的自然语言问题翻译成 BCC 检索式 → 调用脚本执行 → 用通俗语言解读结果。

## 脚本与环境

- 检索入口：`scripts/search.py`（同目录下有 vendored 引擎，直接用 Python 运行）
- 语料目录自动探测；找不到时提示先运行 `scripts/setup.py`
- 首次使用（脚本报 LangSC 未安装等错误）→ 运行 `python scripts/setup.py` 完成环境安装后再重试

## 模式 1：对话检索（默认）

**硬性流程，逐步执行，不得跳步：**

0. **选子命令**（对照下表，拿不准时两个都可先 count 试探）：

| 用户问的是… | 子命令 |
|---|---|
| 多少/几种/最高频/搭配分布 | `freq` |
| 例句/用例/语境/什么样子 | `context` |
| A 和 B 的差别/分工/一样吗 | `compare`（两条检索式） |
| 只要一个总数 | `count` |

1. **读语法**：生成检索式之前，必须先读 `references/bcc_syntax.md` 和 `references/examples.md`（本技能目录内）。若用户问题涉及语言学概念（如"动词""把字句""能愿动词""施事""名词谓语句"等），同时读 `references/linguistics_kb.md` 确认对应 jieba 词性标签或句式特征，再生成检索式。
2. **映射检索式**：把用户问题对照 examples.md 的同型例子**照搬替换**（改词/词性即可）；找不到同型才基于语法自己组合。对比类问题（"A 和 B 的差别/分工"）→ 用 `compare`（两条检索式）。
3. **亮出完整命令**：先用一行告诉用户你将执行的完整命令（含子命令与参数），例如 `python scripts/search.py freq "a的n" --top 30`，再执行。检索式复杂或拿不准时，等用户确认后再执行。
4. **执行**（示例）：
   ```
   python scripts/search.py freq "a的n" --top 30
   python scripts/search.py context "居然" --number 20
   python scripts/search.py compare "很a" "非常a"
   python scripts/search.py freq "很(~){$1=[freq_adv]}" --wordlist "freq_adv=经常 常常 偶尔 时常 往往"
   ```
   输出是 JSON（含 total/records/elapsed_ms）。
5. **解读**（见下方输出规范）。
6. **结果文件（数据库式呈现）**：命中数较多（>30 条）或用户要看全部结果时，重跑一次加 `--export`（默认 **html**，双击打开可🔍搜索、点表头排序；也可 `--export xlsx` 给 Excel 用户）。用户说"导出/数据库/全部结果/Excel"均指此功能。
   **存储目录规则（重要）**：首次导出前，先问用户"检索结果文件想统一存在哪个文件夹？"，用户回答后运行 `python scripts/config.py --results-dir <用户选的路径>` 保存；之后导出默认落该目录，把生成的文件绝对路径告诉用户。若脚本返回 `export_hint`（未配置目录或导出失败），按提示处理后重试，不要自己替用户决定存哪里。

**错误重试环**：返回 `ok:false` 或命中为 0 时——注意 `compare` 的结果没有顶层 total，要看 `items` 里每条的 `count_total`。对照 bcc_syntax.md 检查检索式（90% 是 `*`/`~` 混用或条件语法错）→ 修正重跑，**最多重试 2 轮**。仍失败则如实告诉用户，附上语法速查要点，请用户手写检索式（兜底出口）。**严禁编造检索结果。**

## 模式 2：导入语料

用户说"我有新语料要导入/加入语料库"时：
1. 问清文件位置（文件夹路径），确认是 .doc/.docx/.xlsx/.md/.txt。**注意：Windows 上旧版 .doc 会被跳过**，提前告知用户先用 Word/WPS 批量另存为 .docx
2. 运行 `python scripts/import_corpus.py --source <文件夹>`
3. 成功后报告 JSON 里的 imported/sentences/corpus_files_total/skipped_legacy_doc；如需让改动立即生效可加 `--rebuild`

## 模式 4：删除语料

用户说"删除语料/移除某个文件/清理语料库"时：

1. **先列出语料库现有文件**（让用户选择要删哪个）：
   ```
   python scripts/delete_corpus.py --list
   ```
   返回 `files` 数组，告知用户当前共有多少个文件。

2. **预览将删除的内容**（不加 `--confirm`，安全第一）：
   ```
   python scripts/delete_corpus.py --name 演讲_2024.txt
   python scripts/delete_corpus.py --pattern "演讲_2024*"
   ```
   返回 `preview:true` + `files_to_delete` 列表，**明确告知用户将删除哪些文件及对应映射文件**，等用户确认。

3. **用户确认后执行删除**（加 `--confirm`）：
   ```
   python scripts/delete_corpus.py --name 演讲_2024.txt --confirm
   python scripts/delete_corpus.py --pattern "演讲_2024*" --confirm --rebuild
   ```
   成功后报告 deleted/skipped/corpus_files_total；如需立即生效可加 `--rebuild`。

**红线**：未经用户明确确认不得直接运行带 `--confirm` 的命令。删除不可撤销。

## 模式 3：打开完整界面（兜底）

用户说"打开完整界面/原来的界面/Streamlit"时：
1. 若脚本报 GUI 依赖未安装 → 先运行 `python scripts/setup.py --full`（约 5 分钟）
2. 运行 `python scripts/launch_gui.py`，浏览器打开后告知用户地址（默认 http://localhost:8501；端口被占用时改用 `--port 8502`）

## 解读输出规范（面向文科用户）

- **结论先行**：一两句话直接回答用户的问题（如"'很+形容词'远多于'非常+形容词'，约 3 倍"）
- 数据用**小表格**（词/频次/占比），不超过 15 行，其余用"等"省略
- 例句引用 3-5 条最有代表性的，标注左右文
- 注明统计口径：命中总数、语料为师门演讲语料、jieba 分词标注
- 用户追问（"再看看 XX""换成句式 YY"）→ 回到模式 1 流程继续

## 红线

1. 不读语法文档直接凭感觉写检索式（模型极易写错 BCC 语法）
2. 编造/估算检索结果数字
3. 把脚本报错原文直接甩给用户（要翻译成人话）
