[0m
> build · gpt-5
[0m
开始只读审查。我会先定位并读取 PLAN.md、README.md、SKILL.md、脚本与引用文档、以及 tests/ 下的所有文件，然后输出分条问题清单和总体结论。
[0m✱ [0mGlob "PLAN.md"[90m 1 match[0m
[0m✱ [0mGlob "README.md"[90m 1 match[0m
[0m✱ [0mGlob "skill/bcc-corpus/SKILL.md"[90m 1 match[0m
[0m✱ [0mGlob "skill/bcc-corpus/scripts/*.py"[90m 6 matches[0m
[0m✱ [0mGlob "skill/bcc-corpus/references/*.md"[90m 2 matches[0m
[0m✱ [0mGlob "tests/**/*"[90m 3 matches[0m
[0m→ [0mRead PLAN.md
[0m→ [0mRead README.md
[0m→ [0mRead skill/bcc-corpus/SKILL.md
[0m→ [0mRead skill/bcc-corpus/scripts/import_corpus.py
[0m→ [0mRead skill/bcc-corpus/scripts/launch_gui.py
[0m→ [0mRead skill/bcc-corpus/scripts/search.py
[0m→ [0mRead skill/bcc-corpus/scripts/setup.py
[0m→ [0mRead skill/bcc-corpus/scripts/preprocess.py
[0m→ [0mRead skill/bcc-corpus/scripts/bcc_engine.py
[0m→ [0mRead skill/bcc-corpus/references/examples.md
[0m→ [0mRead skill/bcc-corpus/references/bcc_syntax.md
[0m→ [0mRead tests/testset_engine.json
[0m→ [0mRead tests/testset_translate.json
[0m→ [0mRead tests/run_tests.py
[P0必须改] 功能正确性 | skill/bcc-corpus/scripts/launch_gui.py:20,28-34 | Windows 不兼容：固定使用 venv/bin/python，Win 上应为 venv/Scripts/python.exe，导致 GUI 无法启动 | 复用 setup.py 的 venv_python() 逻辑（抽成公共函数）或在本文件内按平台选择可执行路径

[P0必须改] 功能正确性 | skill/bcc-corpus/scripts/preprocess.py:24-53 | 非 macOS 下 .doc 文件无法处理，但 import_corpus.py/文档宣称支持 .doc；Windows 用户导入 .doc 会直接报错 | 二选一：a) 为 Win/Linux 增加 .doc 转换方案（win32com/antiword/mammoth）；b) 暂不支持则从 import_corpus.py 的 EXTS 去掉 .doc，并在 README/SKILL.md 明确“非 macOS 仅支持 .docx”

[P1建议改] 功能正确性 | skill/bcc-corpus/scripts/preprocess.py:71-96 | read_table_sentences 的 column 参数未生效，仅在表头行 continue，未按列筛选文本 | 解析表头定位 column 索引，仅抽取该列文本；或删除该参数与相关说明，避免误导

[P1建议改] 功能正确性 | skill/bcc-corpus/scripts/search.py:75-82,138-145 | --wordlist 解析失败被误报为“引擎初始化失败”，错误分类与提示不相干 | 单独捕获 ValueError 并返回 {"ok":false,"error":"--wordlist 格式错误","hint":"用法 name=词1 词2"}，不要落入引擎初始化异常分支

[P1建议改] 功能正确性 | skill/bcc-corpus/scripts/setup.py:101-109 | pip 安装失败时仅打印静默输出，用户难以据此采取行动，与 SKILL.md 的“人话提示”不一致 | 捕获安装异常，输出结构化 JSON {"ok":false,"stage":"pip_install","hint": "...重试指引..."}；或至少在异常时补充清晰的中英文指引

[P1建议改] 功能正确性 | skill/bcc-corpus/scripts/import_corpus.py:71-76 | Windows 上删除索引可能因占用失败，未处理 onerror | 使用 shutil.rmtree(idx, onerror=...) 忽略只读/占用并给出“关闭占用进程后重试”的提示

[P2可选] 功能正确性 | skill/bcc-corpus/scripts/search.py:70-73 | make_engine 通过 chdir 改变进程工作目录，若未来集成为长进程工具可能产生副作用 | 用上下文管理器暂时 chdir 或在引擎内部处理路径；至少在注释中强调 CLI-only 假设

[P2可选] 功能正确性 | skill/bcc-corpus/scripts/import_corpus.py:77-84 | ok 仅在 fail==0 时为真，部分失败场景不便于上层判断“已导入多少” | 返回 ok 始终描述整体流程是否完成；新增 partial/warnings 字段表达部分失败

[P0必须改] 结构与可维护性 | skill/bcc-corpus/scripts/launch_gui.py:20 与 skill/bcc-corpus/scripts/setup.py:28-31 | 平台判定与 venv 路径逻辑在两个文件中重复且不一致，造成一处修补另一处遗漏 | 抽取公共工具模块（如 scripts/_env.py）提供 venv_python()，两处复用，减少漂移风险

[P2可选] 结构与可维护性 | skill/bcc-corpus/scripts/import_corpus.py:27 | 常量 MAP_DIR 未使用，易造成读者误解 | 删除未用常量或统一使用该常量生成映射目录路径

[P2可选] 结构与可维护性 | skill/bcc-corpus/scripts/search.py:50-59 | 回退到兄弟项目路径硬编码多层 ..，对目录结构耦合强 | 保留作为开发模式后备，但在注释明确“仅限开发”；推荐通过 BCC_CORPUS 或 BCC_DEV_CORPUS 环境变量覆盖

[P1建议改] 弱模型适配 | skill/bcc-corpus/SKILL.md:33-34 | “错误重试环：ok:false 或 total=0” 未区分 compare 结构（compare 顶层无 total），弱模型易误判 | 文档中补充 compare 判定：检查 items[i].count_total；给出示例与重试指引

[P1建议改] 弱模型适配 | skill/bcc-corpus/SKILL.md:20-29 | 缺少“问题类型→子命令”决策表，弱模型易在 freq/context/compare 之间选错 | 增补决策表：数量/频率/最高/搭配→freq；例句/用法/语境/“什么样子”→context；对比/差别/一样吗/哪个更→compare；仅总数→count

[P1建议改] 弱模型适配 | skill/bcc-corpus/SKILL.md:23 | “亮出检索式”仅展示检索式本身，弱模型仍可能用错子命令 | 要求回显完整命令行（含子命令与参数），用户确认后再执行，如 python scripts/search.py freq "a的n" --top 30

[P2可选] 弱模型适配 | skill/bcc-corpus/SKILL.md:18-34 与 references/*.md | 对比类判别与通配符自查散落在 references，弱模型上下文遗忘概率高 | 在 SKILL.md 模式 1 紧贴步骤 2 添加“对比类判别清单”和“通配符自查清单（最小版）”，减少跨文档跳转

[P1建议改] 测试有效性 | tests/testset_engine.json:54-58 | 未断言 hint 字段，无法保证上层“错误重试环”可用的提示质量 | 在 missing_corpus_graceful 增加对 hint 非空的断言（如 "hint_required": true），或检查返回包含 "hint" 键

[P1建议改] 测试有效性 | tests/testset_engine.json | 缺少 --wordlist 异常路径测试，无法覆盖 search.py 的错误分类修复 | 新增用例：args=["freq","很(~){$1=[bad]}","--wordlist","badformat"]，期望 {"json_valid":true,"ok":false} 且 error 含 "--wordlist 格式"

[P1建议改] 测试有效性 | tests/testset_engine.json:33-35 | compare 仅断言 items_length 与 item_keys，未覆盖数值类型完整性 | 在 compare 用例中断言 items[*].count_total 为数字且存在 freq_distinct

[P2可选] 测试有效性 | tests/run_tests.py:40-43 | 仅解析 stdout 最后一行为 JSON，若中间存在其他 JSON 或未来扩展为分段输出可能误判 | 从末行向前回溯匹配首个可解析的 JSON；或约定 JSON 输出使用固定前缀并据此前缀提取

[P2可选] 测试有效性 | tests/testset_translate.json | 未覆盖 AND/NOT、同词重复等高级条件翻译，弱模型在这些点易犯错 | 增补 2-3 条 AND/NOT 与 $n=$k 的翻译用例（至少做格式自检；有 LLM 时做预验证）

[P2可选] 文档一致性 | README.md:9-10 | “无需安装 Python”在无 Python 的 Windows 机器上可能不成立（setup 仍依赖本地 Python） | 调整为“无需手动配置依赖；首次使用将自动创建虚拟环境。若本机无 Python 3.11+，请先安装或联系维护者”

[P2可选] 文档细节 | skill/bcc-corpus/SKILL.md:46-47 | 仅提示“检查端口占用”，未给出替代端口或命令示例 | 增加“如端口占用，改用 --port 8502”，并给出 lsof/netstat 示例；或在脚本中自动探测可用端口并回显

总体结论：需修改后发布。当前 P0 阻断为 GUI 在 Windows 上不可用与 .doc 导入的跨平台不一致（与文档承诺冲突）。修复 P0 并落地上述 P1（wordlist 错误分类、弱模型 compare 判定说明与测试补强）后可发布。
