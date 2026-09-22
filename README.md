# BCC 语料库检索 Skill

> 面向中文语言学研究与教学的本地语料检索工具：在 WorkBuddy 对话中用自然语言提问，也可以打开 Streamlit 图形界面手写检索式、管理语料和导出结果。

[![GitHub](https://img.shields.io/badge/GitHub-stellaliu0104%2Fbcc--corpus--skill-181717?logo=github)](https://github.com/stellaliu0104/bcc-corpus-skill)

它将 BCC/LangSC 检索能力封装为 Agent Skill，适合对演讲、口传或自行导入的中文文本做可复核的词频、搭配、例句和对比研究。检索与索引均在**用户本机**完成；WorkBuddy 只负责理解问题、生成检索式和解释结果。

## 能做什么

| 能力 | 说明 | 示例问题 |
|---|---|---|
| 词频与搭配 | 查某词、词性组合或结构中的高频词 | “`很` 后面最常接什么形容词？” |
| KWIC 例句 | 返回关键词左右文，查看真实使用语境 | “给我 20 个 `竟然` 的例句” |
| 表达对比 | 比较两种表达的频率与典型搭配 | “`曾经` 和 `已经` 在语料里有什么差别？” |
| 精确计数 | 统计某一检索式的总命中数 | “`居然` 一共出现多少次？” |
| 导出材料 | 导出可搜索、排序的 HTML，或 Excel/CSV | “把全部例句导出 Excel” |
| 导入/删除语料 | 导入自己的文档，或先预览再删除指定语料 | “导入桌面上的访谈稿”“删除 2024 年演讲稿” |
| Streamlit 界面 | 图形化手写查询、浏览结果与管理语料 | “打开完整界面” |

## 快速开始：安装到 WorkBuddy

### 方式 A：上传安装包

1. 下载 GitHub Release 中的 `bcc-corpus.zip`；
2. 在 WorkBuddy 的 **Skills / 技能** 页面上传并启用该 ZIP；
3. 新开一个对话，直接提问，例如：

```text
统计一下“居然”出现多少次，并给我 10 个典型例句。
```

### 方式 B：让 WorkBuddy Agent 自动安装

将下面整段话复制到 WorkBuddy 对话中：

```text
请帮我安装 GitHub 仓库 stellaliu0104/bcc-corpus-skill 中的 bcc-corpus Skill。
仓库地址：https://github.com/stellaliu0104/bcc-corpus-skill
请将 skill/bcc-corpus 安装到 WorkBuddy 的 Skills 目录并启用；如需安装 Python 依赖，请自动完成。
安装完成后，运行一次“统计一下‘居然’出现多少次”验证检索是否可用，并告诉我结果。
```

首次使用时，Skill 会创建本地 Python 虚拟环境、安装 LangSC 等依赖，并在首次检索时建立索引，通常需要数分钟。之后可直接在 WorkBuddy 对话中使用，**对话检索不需要填写第三方模型 API Key**。

> 完整的 WorkBuddy 上传图文步骤见 [`docs/师门使用手册.md`](docs/师门使用手册.md)。

---

## 如何检索语料

### 1. 推荐：直接在 WorkBuddy 对话中提问

不必先学 BCC 检索语法。Agent 会根据问题选择检索方式、执行本地检索，再用表格和例句解释结果。

```text
查一下“竟然”的 20 个例句。

“很”和“非常”后面常接哪些形容词？分别列前 20 个。

“曾经”和“已经”在演讲语料中怎么分工？请比较频率并给出例句。

把“也许”的全部例句导出成可搜索的 HTML 文件。
```

输出会明确统计口径（命中数、语料范围、jieba 分词标注），不会编造检索数字。命中较多或需要写论文留存时，可说“导出”“全部结果”或“Excel”。首次导出前，Agent 会询问你希望把结果统一保存到哪个文件夹。

### 2. 命令行：手写 BCC 检索式

已安装 Skill 后，在 `bcc-corpus` 目录运行以下命令。首次命令行使用如提示环境未就绪，先执行：

```bash
python scripts/setup.py
```

常用检索命令：

```bash
# 统计总命中数
python scripts/search.py count "居然"

# 查看 20 条关键词左右文（KWIC）
python scripts/search.py context "居然" --number 20

# 统计匹配结构的高频词/搭配
python scripts/search.py freq "很a" --top 30

# 对比两条检索式
python scripts/search.py compare "很a" "非常a" --top 20

# 使用自定义词表：查询“很 + 高频副词”类结构
python scripts/search.py freq '很(~){$1=[freq_adv]}' \
  --wordlist 'freq_adv=经常 常常 偶尔 时常 往往'
```

所有命令返回 JSON，便于 Agent 或其他程序读取。可加 `--pretty` 查看格式化 JSON。BCC 检索式与更多示例见：

- [`skill/bcc-corpus/references/bcc_syntax.md`](skill/bcc-corpus/references/bcc_syntax.md)
- [`skill/bcc-corpus/references/examples.md`](skill/bcc-corpus/references/examples.md)

### 3. 导出检索结果

默认推荐交互式 HTML：双击可打开、文本筛选、点击表头排序；也支持 `xlsx` 和 `csv`。

```bash
# 默认导出 HTML
python scripts/search.py context "居然" --export

# 导出 Excel
python scripts/search.py context "居然" --export xlsx

# 本次直接指定输出文件路径
python scripts/search.py freq "很a" --export html --out ~/Desktop/hen-a.html
```

### 4. 打开 Streamlit 完整界面

适合需要手写检索式、可视化操作或批量管理语料的场景：

```bash
# 首次打开完整界面，安装 GUI 依赖
python scripts/setup.py --full

# 启动界面（默认 http://localhost:8501）
python scripts/launch_gui.py
```

也可以在 WorkBuddy 对话中说：

```text
打开完整界面
```

Streamlit 的**基础检索**和**语料管理**不需要 API Key。其“AI 分析”页是独立模型调用；如要使用，可在界面中配置 DeepSeek、GLM、OpenAI-compatible 或 Claude 的个人凭证。请不要把密钥提交到 GitHub 或发到群聊。

---

## 管理自己的语料

### 导入

支持 `.doc`、`.docx`、`.xlsx`、`.md`、`.txt`。将源文件放进一个文件夹后：

```bash
python scripts/import_corpus.py --source ~/Desktop/新语料 --rebuild
```

- 导入后生成适用于 BCC 的已分词标注文本；
- `--rebuild` 会删除旧索引，下一次检索自动重建；
- macOS 可以处理旧版 `.doc`；Windows/Linux 请先用 Word/WPS 将 `.doc` 另存为 `.docx`；
- Agent 模式下只需说“我有新语料要导入，文件在……”。

### 删除（必须先预览，再确认）

```bash
# 查看现有语料
python scripts/delete_corpus.py --list

# 预览：不会实际删除
python scripts/delete_corpus.py --name 演讲_2024.txt

# 明确确认后才删除，并让下次检索重建索引
python scripts/delete_corpus.py --name 演讲_2024.txt --confirm --rebuild
```

也可用 `--pattern "演讲_2024*"` 批量匹配。删除不可撤销，因此不带 `--confirm` 时只会返回待删除清单。

### 数据归属与隐私

你的个人语料、索引和导出目录都保留在本机：

| 目录 | 内容 | 是否自动上传 |
|---|---|---|
| `data/Corpus/` | 导入后的可检索语料 | 否 |
| `data/CorpusIdx/` | 本地检索索引 | 否 |
| `data/_maps/` | 导入文件与处理结果的映射 | 否 |
| `app/config/` | Streamlit 本地设置和模型配置 | 否 |

共享语料请由维护者审核后单独发布。导入前请确认文件可在当前电脑保存，并遵守团队的数据使用规范。

---

## 一键更新到最新版本

普通版本更新不需要重新上传 Skill，也不会覆盖你的语料。在 WorkBuddy 对话中说：

```text
更新 BCC 语料库
```

Agent 会先检查版本，告知变更后等待确认：

```bash
python scripts/update.py --check
python scripts/update.py
```

更新器从本仓库最新 GitHub Release 下载名为 `bcc-corpus.zip` 的附件，校验压缩包结构后仅替换程序文件。它**不会上传或读取你的私有语料，不会执行下载包中的脚本**，并会保留：

- `data/Corpus/`：自己导入的语料；
- `data/CorpusIdx/`：本地索引；
- `app/config/`：界面设置和本地模型配置；
- `venv/`：本地 Python 环境与已安装依赖。

更新完成后应运行一次基础检索验证。更新前请关闭正在运行的 Streamlit 页面或检索任务；若新版新增 GUI 依赖，再执行：

```bash
python scripts/setup.py --full
```

> 注意：一键更新要求维护者已创建 GitHub Release 并上传 `bcc-corpus.zip`。仅推送代码到 `main` 分支不会触发用户端更新。

---

## 维护者发布新版

每次发布可更新的版本：

```bash
# 1) 修改 skill/bcc-corpus/VERSION，例如 1.2.0
# 2) 测试并打包；--corpus 指向要随“首次安装包”分发的共享语料目录
python3 tools/package.py --corpus /path/to/Corpus

# 3) 提交和推送代码，创建 tag，例如 v1.2.0
# 4) 在 GitHub 创建同名 Release，并上传生成的 skill/bcc-corpus.zip
```

Release 附件名必须严格为 **`bcc-corpus.zip`**，且包内 `VERSION` 应与 Release 对应。用户端更新器只识别此附件名。

为避免覆盖个人资料，常规程序升级不会更新 `data/Corpus/`。如需发布共享语料，请明确单独提供语料包或在首次安装包中发布，并在 Release 说明中写清范围与来源。

---

## 开发与测试

```bash
# L1：检索引擎测试（需已经建立 venv 并安装 LangSC）
./venv/bin/python tests/run_tests.py --corpus ../bcc-ai-tool-mac/data/Corpus

# L2：翻译层预验证（可选，需要 GLM 配置）
./venv/bin/python tests/run_tests.py --suite translate --llm zhipuai
```

## 来源与致谢

- 引擎封装参考 `bcc-ai-tool-mac` 中的 `core/bcc_engine.py`；
- 检索能力基于 [LangSC](https://pypi.org/project/LangSC/) 的 BCC 实现。
