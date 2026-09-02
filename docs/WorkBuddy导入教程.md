# WorkBuddy 导入 BCC 语料库技能 · 图文教程（文字版）

> 适用对象：维护者（首次验证）与师门成员（日常安装）
> 前置条件：已安装 WorkBuddy App（[官网 workbuddy.ai](https://www.workbuddy.ai)，Windows/Mac 均有）

---

## 第一步：组装技能包（只需维护者做一次）

技能代码在仓库 `skill/bcc-corpus/`，但语料不入库，需要组装一次完整包。

在仓库根目录执行一条命令（脚本自动拷语料、排除 venv/索引/配置、**中文文件名带 UTF-8 标志防 Windows 乱码**）：

```bash
cd "/Users/I765069/Documents/300-Coding/302-projects/BCC document/bcc-corpus-skill"
python3 tools/package.py
# 输出: 打包完成: skill/bcc-corpus.zip (约 801 个条目, 18M)
```

组装完的 `bcc-corpus.zip`（约 25-30M，含 55M 语料压缩后）就是发给师门的安装包。

**要不要带索引？** 不带。首次检索自动建索引（实测约 20 秒，一次性），包小好传输（实测仅 18M）。

## 第二步：导入 WorkBuddy

### 方式 A：技能市场上传（推荐，师门用这个）

1. 打开 WorkBuddy，进入 **设置 → 技能（Skills）/ 技能市场**
2. 点 **添加技能 → 上传技能**
3. 把 `bcc-corpus.zip` 拖进窗口（或点击选择文件）
4. 显示导入成功即可——系统自动完成配置，无需额外操作
5. 在技能列表里能看到 `bcc-corpus`，确认开关是"启用"状态

### 方式 B：手动放置（备选，适合会开终端的人）

```bash
# Mac
mkdir -p ~/.workbuddy/skills && cp -R bcc-corpus ~/.workbuddy/skills/
# Windows(PowerShell)
New-Item -ItemType Directory -Force ~\.workbuddy\skills | Out-Null
Copy-Item -R bcc-corpus ~\.workbuddy\skills\
```
重启 WorkBuddy 生效。

## 第三步：首次使用验证

对 WorkBuddy 说（任选其一）：

| 说什么 | 期待发生什么 |
|---|---|
| **"帮我初始化 BCC 语料库工具"** | 它运行 setup 自动建环境装依赖（2-8 分钟，一次性的）|
| **"统计一下'居然'出现多少次"** | 回答一个数字（说明检索引擎通了）|
| **"'很'和'非常'修饰形容词有什么差别"** | 给出对比表格（说明 AI 翻译+解读全链路通了）|

首次检索会建索引（实测 779 个语料文件约 **20 秒**，一次性），之后就快了（毫秒级）。

## 第四步：日常使用（师门看这里）

直接用大白话问就行，例如：

- "帮我查'竟然'的 20 个例句"
- "'把'字句里'把'后面一般接什么名词？"
- "我有新语料要导入，在桌面/新语料 文件夹" ← 师妹维护语料用这句
- "打开完整界面" ← 想用原来的网页版界面时

## 常见问题

| 现象 | 原因与解法 |
|---|---|
| 导入后没反应/技能没出现 | 重启 WorkBuddy；确认技能开关是"启用" |
| 首次初始化失败 | 多为网络问题（要联网装依赖）；对着 WorkBuddy 说"重试初始化" |
| 说"打开完整界面"报 GUI 依赖未装 | 说"完整安装环境"（即 setup --full，约 5 分钟）|
| 导入语料时旧版 .doc/.xls 被跳过 | Windows 不支持旧格式：用 Word/WPS/Excel 批量另存为 .docx/.xlsx 再导 |
| 检索报"未找到语料目录" | 技能包没带 data/Corpus（组装时漏了第一步），重新打包 |
| 结果和预期差很远 | 检索式可能错了——追问 WorkBuddy"你用的检索式是什么"，可让它改用你手写的检索式 |

---

## 维护者备忘

- 测试集在仓库 `tests/`，换机型/换 WorkBuddy 模型后重跑：
  `python tests/run_tests.py`（引擎层）和 `--suite translate --llm`（翻译层）
- 师门真实提问失败案例 → 回流到 `references/examples.md` 示例库，越用越准
- 发新版给师门：重跑第一步的 zip 命令 → 微信发新 zip → 师门重新"上传技能"覆盖
