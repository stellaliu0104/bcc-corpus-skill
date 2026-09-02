# BCC 语料库检索技能（WorkBuddy Skill）

给文科师门用的 BCC 语料库检索工具，打包为 WorkBuddy 技能。师门成员只需：

1. 安装 WorkBuddy（[Win/Mac](https://www.workbuddy.ai)）
2. 技能市场 → 上传技能 → 导入本技能包 zip
3. 对话框直接提问，例如 *"'曾经'和'已经'在演讲语料里怎么分工？"*

无需手动配置任何依赖：首次使用技能会自动创建虚拟环境并安装（若本机没有 Python 3.11+，会引导安装）。无需申请任何 API key。

## 三模式

| 模式 | 触发说法 | 行为 |
|---|---|---|
| 1 对话检索（默认） | 任何语料/检索/搭配/对比问题 | agent 生成 BCC 检索式 → `scripts/search.py` 执行 → 聊天中解读 |
| 2 导入语料 | "我有新语料要导入" | `scripts/import_corpus.py` 转换 doc/docx 入库 |
| 3 完整界面 | "打开完整界面" | `scripts/launch_gui.py` 拉起原 Streamlit 界面（兜底） |

## 开发

```bash
# 测试（L1 引擎层，需已建 venv 并安装 LangSC）
./venv/bin/python tests/run_tests.py --corpus ../bcc-ai-tool-mac/data/Corpus

# L2 翻译层预验证（可选，用 GLM 验证测试集与提示词质量）
./venv/bin/python tests/run_tests.py --suite translate --llm zhipuai
```

## 来源与致谢

- 引擎封装 vendored 自 [bcc-ai-tool-mac](../bcc-ai-tool-mac)（`core/bcc_engine.py`）
- 检索能力基于 [LangSC](https://pypi.org/project/LangSC/) 的 BCC 实现
