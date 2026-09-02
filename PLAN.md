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
- [x] commit 6+: 实测修复循环
- [x] commit 7: setup/import/launch（模式2/3）
- [x] commit 8: L2 翻译层 GLM 预验证
- [ ] GitHub push（阻塞：token 失效）
- [ ] WorkBuddy 真机导入验证（用户侧）
- [ ] HY3 翻译准确率实测（用户侧）
- [ ] 分发 zip 组装脚本
