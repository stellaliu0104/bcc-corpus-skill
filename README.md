# BCC Corpus Skill

> 一个可安装到本地 Agent 的中文语料库检索 Skill。用自然语言完成词频、搭配、KWIC 例句与表达对比；也可使用 Streamlit 图形界面手写 BCC 检索式、导入语料和导出研究材料。

[![GitHub](https://img.shields.io/badge/GitHub-stellaliu0104%2Fbcc--corpus--skill-181717?logo=github)](https://github.com/stellaliu0104/bcc-corpus-skill)
[![Release](https://img.shields.io/github/v/release/stellaliu0104/bcc-corpus-skill?label=release)](https://github.com/stellaliu0104/bcc-corpus-skill/releases)

`bcc-corpus` 的本质是一个 **Agent Skill**，不是 WorkBuddy 专属应用：Agent 负责理解研究问题、选择检索策略和解释结果；Skill 在本机运行 Python 与 LangSC/BCC 引擎，语料、索引和导出文件均保存在本机。

适用于 **Pi / Sol-Pi、Claude Code、Codex、WorkBuddy**，以及其他同时具备以下能力的 Agent：

1. 能加载包含 `SKILL.md` 的本地 Skill；
2. 能读取 Skill 目录中的参考资料并执行本地 Python 命令；
3. 首次使用时允许创建虚拟环境、安装 Python 依赖；
4. 需要完整界面时，能访问本机浏览器的 `localhost`。

> Agent 的 Skill 安装路径与刷新方式因产品、版本和团队策略而不同。请优先遵循你的 Agent 官方 Skill 安装说明；仓库和安装包内的实际 Skill 根目录均为 `skill/bcc-corpus/`。

---

## 能做什么

| 能力 | 说明 | 示例提问 |
|---|---|---|
| 词频与搭配 | 查询词、词性组合或结构中的高频词 | “`很` 后面最常接什么形容词？” |
| KWIC 例句 | 返回关键词左右文，查看真实使用语境 | “给我 20 个 `竟然` 的例句。” |
| 表达对比 | 比较两种表达的频率与典型搭配 | “`曾经` 和 `已经` 在语料里有什么差别？” |
| 精确计数 | 统计某一检索式的总命中数 | “`居然` 一共出现多少次？” |
| 导出材料 | 导出可搜索、排序的 HTML，或 Excel/CSV | “把全部例句导出 Excel。” |
| 导入 / 删除语料 | 导入自己的文本；删除前先预览、确认后执行 | “导入桌面的访谈稿。” |
| Streamlit 界面 | 图形化手写查询、浏览结果、管理语料 | “打开完整界面。” |

## 工作方式与边界

```text
你的自然语言研究问题
          ↓
当前 Agent：读 SKILL.md / 参考语法，生成或选择 BCC 检索式
          ↓
bcc-corpus 本地脚本：在本地语料上检索，输出 JSON
          ↓
当前 Agent：基于真实结果解释、制表、导出
```

- **不依赖 Agent 的 API Key**：日常检索由当前 Agent 的对话模型推理；本地检索脚本不读取、复制或转发 Agent 的 OAuth / API 凭证。
- **本机处理数据**：语料、索引、配置和导出结果默认不上传至 GitHub、Agent 服务或其他成员电脑。
- **结果可复核**：脚本输出 JSON；Skill 要求 Agent 先读语法参考、展示执行命令、不得编造频次或例句。
- **Streamlit 的 AI 分析页是可选功能**：基础检索和语料管理不需要 Key；若在该页直接调用 DeepSeek、GLM、OpenAI-compatible 或 Claude，需要用户自行配置该服务商的 Key，且只保存于本机。

---

## 安装

### 常用 Agent：一键安装命令

下面的命令从 GitHub **最新 Release** 下载完整 `bcc-corpus.zip`（包括脚本、语法参考、界面与共享语料），并放进各平台官方支持的**用户级 Skill 目录**。运行完毕后，重新打开 Agent；首次触发检索时，Agent 会按 `SKILL.md` 运行 `python scripts/setup.py` 完成本地环境初始化。

> **macOS / Linux（需要 `curl` 与 `unzip`）**：命令在临时目录下载并解压 Release，随后只复制 `bcc-corpus/`。不要用普通 Git clone 替代：仓库为避免提交大型语料，不保存 `data/Corpus/`；可用的完整安装包在 Release 中。

#### Pi / Sol-Pi

Pi 官方会扫描 `~/.pi/agent/skills/` 和跨 Agent 通用的 `~/.agents/skills/`。本命令安装到后者，因此 Pi 与遵循该目录的 Codex 都可发现：

```bash
tmp=$(mktemp -d) && curl -fL https://github.com/stellaliu0104/bcc-corpus-skill/releases/latest/download/bcc-corpus.zip -o "$tmp/bcc-corpus.zip" \
  && unzip -q "$tmp/bcc-corpus.zip" -d "$tmp" \
  && rm -rf ~/.agents/skills/bcc-corpus \
  && mkdir -p ~/.agents/skills \
  && cp -R "$tmp/bcc-corpus" ~/.agents/skills/ \
  && rm -rf "$tmp"
```

重启 Pi 后，可输入：

```text
/skill:bcc-corpus 查一下“竟然”的 20 个例句
```

也可直接自然语言提问，让 Pi 自动匹配该 Skill。

#### Codex CLI / Codex IDE

Codex 官方扫描 `~/.agents/skills/`；如果已经运行过上面的 Pi / Sol-Pi 命令，**不必重复安装**。单独安装时运行：

```bash
tmp=$(mktemp -d) && curl -fL https://github.com/stellaliu0104/bcc-corpus-skill/releases/latest/download/bcc-corpus.zip -o "$tmp/bcc-corpus.zip" \
  && unzip -q "$tmp/bcc-corpus.zip" -d "$tmp" \
  && rm -rf ~/.agents/skills/bcc-corpus \
  && mkdir -p ~/.agents/skills \
  && cp -R "$tmp/bcc-corpus" ~/.agents/skills/ \
  && rm -rf "$tmp"
```

重启 Codex 后使用 `/skills` 查看，或在提示中显式写：

```text
$bcc-corpus 查一下“竟然”的 20 个例句
```

也可以把目录放在当前项目的 `.agents/skills/bcc-corpus/`，使其仅对该项目生效：

```bash
tmp=$(mktemp -d) && curl -fL https://github.com/stellaliu0104/bcc-corpus-skill/releases/latest/download/bcc-corpus.zip -o "$tmp/bcc-corpus.zip" \
  && unzip -q "$tmp/bcc-corpus.zip" -d "$tmp" \
  && mkdir -p .agents/skills \
  && rm -rf .agents/skills/bcc-corpus \
  && cp -R "$tmp/bcc-corpus" .agents/skills/ \
  && rm -rf "$tmp"
```

#### Claude Code

Claude Code 的用户级 Skill 目录是 `~/.claude/skills/`：

```bash
tmp=$(mktemp -d) && curl -fL https://github.com/stellaliu0104/bcc-corpus-skill/releases/latest/download/bcc-corpus.zip -o "$tmp/bcc-corpus.zip" \
  && unzip -q "$tmp/bcc-corpus.zip" -d "$tmp" \
  && rm -rf ~/.claude/skills/bcc-corpus \
  && mkdir -p ~/.claude/skills \
  && cp -R "$tmp/bcc-corpus" ~/.claude/skills/ \
  && rm -rf "$tmp"
```

Claude Code 通常可自动发现目录变更；未出现时重开会话并运行 `/skills`。显式调用：

```text
/bcc-corpus 查一下“竟然”的 20 个例句
```

只给某个项目安装时，将目标目录改为该项目根目录的 `.claude/skills/bcc-corpus/` 即可。

#### WorkBuddy

下载 [Release](https://github.com/stellaliu0104/bcc-corpus-skill/releases) 中的 `bcc-corpus.zip`，从 WorkBuddy 的 **Skills / 技能** 页面上传并启用。图文步骤见 [`docs/师门使用手册.md`](docs/师门使用手册.md)。

### 方式 B：让当前 Agent 安装

不想在终端执行命令时，将下列提示直接交给当前 Agent：

```text
请安装 BCC Corpus Skill 的最新 Release。
Release 页面：https://github.com/stellaliu0104/bcc-corpus-skill/releases
请下载最新 Release 的 bcc-corpus.zip；解压后，依据你所在平台的 Skill 安装规范，将完整的 bcc-corpus 目录安装为本地 Skill 并启用。不要只 clone 仓库源码，因为共享语料在 Release ZIP 中。
如需 Python 环境，请在该 Skill 目录运行 python scripts/setup.py；安装完成后执行：
python scripts/search.py count "居然"
请报告检索结果或真实的安装错误，不要编造结果。
```

安装后，如果 Agent 不会自动发现新 Skill，请按该平台要求刷新 Skills、重开会话或重启 Agent。

### 方式 C：从 GitHub Release 下载

从 [Releases](https://github.com/stellaliu0104/bcc-corpus-skill/releases) 下载 `bcc-corpus.zip`：

- **WorkBuddy**：可在 Skills / 技能页直接上传 ZIP；具体图文步骤见 [`docs/师门使用手册.md`](docs/师门使用手册.md)。
- **Pi / Codex / Claude Code 等**：如不使用上面的 Git 命令，可解压后把完整的 `bcc-corpus/` 放到平台规定的本地 Skill 目录；不要只复制 `SKILL.md`，还需要 `scripts/`、`references/`、`app/` 和 `data/`。

首次运行需要创建本地 Python 虚拟环境、安装 LangSC 等依赖，并在首次检索时建立索引，通常需要数分钟：

```bash
cd /path/to/bcc-corpus
python scripts/setup.py
```

如需 Streamlit 完整界面，改用：

```bash
python scripts/setup.py --full
```

---

## 如何检索语料

### 1. 直接向 Agent 提问（推荐）

无需先学习 BCC 检索语法。已启用 Skill 的 Agent 会把自然语言问题映射为检索式、运行本地命令，并依据真实输出解读。

```text
查一下“竟然”的 20 个例句。

“很”和“非常”后面常接哪些形容词？分别列前 20 个。

“曾经”和“已经”在演讲语料中怎么分工？请比较频率并给出例句。

把“也许”的全部例句导出成可搜索的 HTML 文件。
```

每次成功查询后，Skill 会自动在浏览器打开一个本机 **“BCC 全部检索结果”** 页面：

- 自动补拉同一检索式的全部 KWIC 命中（安全上限 5000 条）；
- 列表只展示查询目标所在句及其前后共约 **50 字**，查询目标以黄色高亮；
- 点击“查看完整段落”才展开完整语境：由于发布语料已按句切分、原始段落边界不再保留，页面展示的是以命中词为中心前后各最多 **200 个连续字符**；
- 展示语料文件出处与行号；出处由检索引擎返回或在本机原始语料中回查；`未定位` 不代表没有命中，而是引擎未返回来源且本地 KWIC 片段无法可靠唯一匹配某个源文件，因此不会伪造来源；
- 页面可按命中句或出处筛选，点击列标题排序，并按 **每页 50 条** 翻页；
- 页面内可直接点击“导出 CSV（Excel 可打开）”或“导出 HTML”，只导出当前筛选后的记录；下载的导出文件由用户浏览器保存；
- 页面本身是临时文件：下一次查询会清理上一轮页面，超过 24 小时也会清理。静态本地 HTML 无法可靠感知标签页关闭，因此不能承诺“关闭标签页瞬间删除”；用户点击导出的下载文件不会被清理。

Agent 对话中仍会给出摘要、统计口径（命中数、语料范围、jieba 分词标注）与代表例句；完整记录以自动打开的结果页为准。正常查询不会额外保存文件。只有用户明确要求“导出到指定目录”或“另存文件”时，Agent 才使用命令行 `--export` 生成额外文件，并在首次使用时询问保存目录。

### 2. 命令行：手写 BCC 检索式

在 `bcc-corpus` 根目录运行。首次使用如提示环境未就绪，先执行 `python scripts/setup.py`。

```bash
# 统计总命中数
python scripts/search.py count "居然"

# 查看 20 条关键词左右文（KWIC）；同时自动打开全部命中、完整句与出处页面
python scripts/search.py context "居然" --number 20

# 统计匹配结构的高频词 / 搭配
python scripts/search.py freq "很a" --top 30

# 对比两条检索式
python scripts/search.py compare "很a" "非常a" --top 20

# 自定义词表
python scripts/search.py freq '很(~){$1=[freq_adv]}' \
  --wordlist 'freq_adv=经常 常常 偶尔 时常 往往'
```

脚本默认输出 JSON，可加 `--pretty` 格式化查看。检索语法与可直接套用的示例见：

- [`skill/bcc-corpus/references/bcc_syntax.md`](skill/bcc-corpus/references/bcc_syntax.md)
- [`skill/bcc-corpus/references/examples.md`](skill/bcc-corpus/references/examples.md)
- [`skill/bcc-corpus/references/linguistics_kb.md`](skill/bcc-corpus/references/linguistics_kb.md)

> 如在无图形桌面的服务器或自动化任务中运行，可加 `--no-results-page` 关闭浏览器结果页；正常的 Agent 查询不应使用此参数。

### 3. 导出检索结果

默认推荐交互式 HTML：双击即可打开、文本筛选、点击表头排序；也支持 `xlsx` 与 `csv`。

```bash
# 默认导出 HTML
python scripts/search.py context "居然" --export

# 导出 Excel
python scripts/search.py context "居然" --export xlsx

# 本次直接指定输出文件路径
python scripts/search.py freq "很a" --export html --out ~/Desktop/hen-a.html
```

### 4. Streamlit 完整界面

适合手写检索式、可视化操作或批量管理语料：

```bash
# 首次使用 GUI 时安装依赖
python scripts/setup.py --full

# 启动（默认 http://localhost:8501）
python scripts/launch_gui.py
```

也可以直接对当前 Agent 说“打开完整界面”。基础检索、导入和删除语料都不需要模型 Key；只有页面内的“AI 分析”使用独立服务商 API。

---

## 管理自己的语料

### 导入

支持 `.doc`、`.docx`、`.xlsx`、`.md`、`.txt`。将源文件放进同一个文件夹后：

```bash
python scripts/import_corpus.py --source ~/Desktop/新语料 --rebuild
```

- 导入后会生成适用于 BCC 的已分词标注文本；
- `--rebuild` 删除旧索引，下一次检索自动重建；
- macOS 可以处理旧版 `.doc`；Windows/Linux 请先用 Word/WPS 将 `.doc` 另存为 `.docx`；
- 使用 Agent 时，只需说“我有新语料要导入，文件在……”。

### 删除：必须先预览，再确认

```bash
# 列出现有语料
python scripts/delete_corpus.py --list

# 预览，不会实际删除
python scripts/delete_corpus.py --name 演讲_2024.txt

# 明确确认后才删除，并让下次检索重建索引
python scripts/delete_corpus.py --name 演讲_2024.txt --confirm --rebuild
```

也可使用 `--pattern "演讲_2024*"` 批量匹配。删除不可撤销；不带 `--confirm` 只会显示待删除清单。

### 本地数据与隐私

| 目录 | 内容 | 自动上传？ |
|---|---|---|
| `data/Corpus/` | 导入后的可检索语料 | 否 |
| `data/CorpusIdx/` | 本地检索索引 | 否 |
| `data/_maps/` | 导入文件与处理结果的映射 | 否 |
| `app/config/` | Streamlit 本地设置与可选的模型配置 | 否 |

共享语料应由维护者审核后单独发布。导入前请确认文件允许保存在当前电脑，并遵守团队的数据使用规范。

---

## 更新到最新版本

可以对当前 Agent 说：

```text
更新 BCC 语料库。
```

Skill 会先检查 GitHub Release 版本，在你确认后更新：

```bash
python scripts/update.py --check
python scripts/update.py
```

更新器只从本仓库最新 GitHub Release 下载名为 `bcc-corpus.zip` 的附件，验证压缩包路径后仅替换程序文件。它不会执行下载包中的脚本，也不会覆盖以下本地数据：

- `data/Corpus/`：自行导入的语料；
- `data/CorpusIdx/`：本地索引；
- `app/config/`：界面设置与模型配置；
- `venv/`：本地 Python 环境与已安装依赖。

更新前请关闭正在运行的 Streamlit 或检索任务。若新版本增加 GUI 依赖，运行：

```bash
python scripts/setup.py --full
```

> 更新器使用 GitHub Releases，而不是 `main` 分支；维护者仅推送代码时，用户端不会检测为可更新版本。

---

## 平台适配说明

| Agent / 平台 | 适配状态 | 使用方式 |
|---|---|---|
| Pi / Sol-Pi | 支持 | 依照 Pi 的 Skill 发现规则安装 `bcc-corpus/`；Agent 读取 `SKILL.md` 后执行本地脚本。 |
| Claude Code | 支持 | 按 Claude Code 的本地 Skill 规范安装目录；首次运行允许执行 `scripts/setup.py`。 |
| Codex | 支持 | 按 Codex 的 Agent/Skill 配置规范安装目录；需要允许 shell/Python 与本机文件访问。 |
| WorkBuddy | 支持 | 可导入 Release ZIP，或按其 Skill 目录规则安装；WorkBuddy 专用教程见下方链接。 |
| 其他本地 Agent | 通常支持 | 满足本 README 开头的四项能力即可；目录规则由该 Agent 决定。 |

兼容性指的是**Skill 的检索能力**：不同 Agent 的安装入口、权限确认、Skill 刷新方式与浏览器打开方式由平台自身控制。若某平台不允许执行本地 Python、创建 venv 或访问本机文件，则无法直接运行本 Skill。

### WorkBuddy 专用文档

WorkBuddy 用户可参考：

- [`docs/师门使用手册.md`](docs/师门使用手册.md)：面向普通使用者的安装与研究流程；
- [`docs/WorkBuddy导入教程.md`](docs/WorkBuddy导入教程.md)：面向维护者的打包与上传说明。

---

## 维护者发布新版

```bash
# 1) 修改 skill/bcc-corpus/VERSION，例如 1.2.0
# 2) 测试并打包；--corpus 指向随首次安装包分发的共享语料目录
python3 tools/package.py --corpus /path/to/Corpus

# 3) 提交并推送代码，创建 tag，例如 v1.2.0
# 4) 在 GitHub 创建同名 Release，上传生成的 skill/bcc-corpus.zip
```

Release 附件名必须严格为 **`bcc-corpus.zip`**，且包内 `VERSION` 应与 Release 对应。更新器只识别该附件名。

为避免覆盖个人资料，常规程序升级不更新 `data/Corpus/`。需要发布共享语料时，应单独提供语料包，或在首次安装包中携带，并在 Release 说明中写清范围、来源和更新方式。

---

## 开发与测试

```bash
# L1：检索引擎测试（需已建立 venv 并安装 LangSC）
./venv/bin/python tests/run_tests.py --corpus ../bcc-ai-tool-mac/data/Corpus

# L2：翻译层预验证（可选，需要单独配置 GLM 或兼容服务）
./venv/bin/python tests/run_tests.py --suite translate --llm zhipuai
```

## 来源与致谢

- 引擎封装参考 `bcc-ai-tool-mac` 中的 `core/bcc_engine.py`；
- 检索能力基于 [LangSC](https://pypi.org/project/LangSC/) 的 BCC 实现。
