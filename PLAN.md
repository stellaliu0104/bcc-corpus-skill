# PLAN — bcc-corpus-skill

> 目标：把 `bcc-ai-tool-mac` / `bcc-ai-tool-win` 合并改造为一个 WorkBuddy 技能包，让文科师门零门槛使用 BCC 语料库检索。
> 讨论记录见 `../01-notes/`，WorkBuddy 调研见 `../02-research/`。

## 架构：一个 Skill、三模式

```
skill/bcc-corpus/
├── SKILL.md              # 技能定义（三模式路由 + 弱模型防御流程）
├── scripts/
│   ├── bcc_engine.py     # vendored 自 bcc-ai-tool-mac/core/bcc_engine.py
│   ├── search.py         # 模式1: CLI 检索入口（freq/context/count/compare --format json）
│   ├── setup.py          # 环境自检+安装（win/mac 自适应）
│   ├── import_corpus.py  # 模式2: 导入新语料（doc/docx → data/Corpus）
│   └── launch_gui.py     # 模式3: 拉起 Streamlit 完整界面（兜底）
├── references/
│   ├── bcc_syntax.md     # BCC 检索语法（自 grammar/bcc_syntax.md）
│   └── examples.md       # 30+ 条"研究问题→检索式"对照示例库
└── app/                  # vendored Streamlit 应用（模式3 用）
```

## 弱模型（HY3）四层防御

1. SKILL.md 强制流程：生成检索式前必读 references，输出前自查规则
2. examples.md 示例库：模型做模式匹配，不做自由创作
3. 校验-重试环：search.py 返回结构化错误 → agent 自查重写重试（≤2轮）
4. 降级出口：用户手写/编辑检索式

## 测试

- `tests/run_tests.py`（零依赖 plain runner）
- L1 引擎层：`testset_engine.json` — 检索式 → 结果断言（确定性，今晚跑）
- L2 翻译层：`testset_translate.json` — 自然语言问题 → 预期检索式（WorkBuddy/HY3 真机后跑；可选 --llm zhipuai 用 GLM 预验证测试集质量）

## 语料与索引

- 语料不在 git 内（.gitignore data/）；分发时打包脚本组装 zip（语料 55M 预转换 txt；索引 293M 可选）
- 开发/测试：直接指向兄弟目录 `../bcc-ai-tool-mac/data/Corpus`（复用已建索引）

## 提交规范

小步快跑：一个 commit 一个 feature。GitHub: stellaliu0104/bcc-corpus-skill（待 gh 重新认证 github.com 后推送）。

## 状态

- [x] 方案确认（2026-09-02）
- [x] commit 1: 骨架 + PLAN/README/.gitignore
- [x] commit 2: vendor 引擎
- [x] commit 3: search.py CLI
- [x] commit 4: SKILL.md + references
- [x] commit 5: 测试集 + runner
- [x] commit 6+: 实测修复循环（argparse 父解析器、语料目录语义、corpus 回退层级）
- [x] commit 7: setup/import/launch（模式2/3）+ vendored app（HTTP 200 实测）
- [x] commit 8: L2 翻译层 GLM-5.3 预验证 → 16/16
- [x] 跨模型审查循环：gpt-5 两轮（R1"需修改后发布"→ P0×3/P1×9 全部修复 → R2"**可发布**"）
- [ ] GitHub push（阻塞：本机 github.com token 失效，待 `gh auth login -h github.com`）
- [ ] WorkBuddy 真机导入验证（已通过一轮 compare 全数字核验，待覆盖模式2/3）
- [ ] HY3 翻译准确率实测（用户侧，用 tests/testset_translate.json --llm）
- [x] 分发 zip 组装脚本（tools/package.py，含 UTF-8 中文名修复——macOS 自带 zip 会让 774 个中文文件名在 Windows 解压乱码，已用 Python zipfile 修复并验证）

## 实测关键指标（2026-09-02 晚）

- 索引冷加载：**0.2s**（复用 CorpusIdx，路径 B 速度顾虑消除）
- L1 引擎层：12/12（含错误路径与数值完整性断言）
- L2 翻译层（GLM-5.3 当翻译器）：16/16；**运行间方差 14~16/16**（temperature=0 仍有思考路径抖动），后续应引入多次运行稳定性指标
- 模式 2 导入：doc/docx/xlsx/md/txt → GBK+标注 ✓（Windows 旧 .doc/.xls 诚实跳过）
- 模式 3 GUI：HTTP 200 ✓

## 遗留技术疑点

- BCC `NOT` 复合语义存疑：`n们`=2763 但 `n们 NOT r们`=0，需查 LangSC 文档/DLL 行为后再加 NOT 翻译测试用例
