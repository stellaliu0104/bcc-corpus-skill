# -*- coding: utf-8 -*-
"""BCC AI 语料库工具 —— Streamlit 主界面。

三个 tab:
  1. 基础检索  —— 手写 BCC 检索式(可靠兜底)
  2. AI 分析   —— 中文提问 → AI 生成检索式(可编辑) → 检索 → AI 解读
  3. 语料管理  —— 导入语料/索引、查看状态
"""

import os
import sys

import pandas as pd
import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
# LangSC 的 BCC 只接受相对路径(内部会给路径前缀 "./"),因此固定工作目录到项目根,
# 再用相对路径 data/Corpus,避免绝对路径被拼成 ".//Users/..." 而失效。
os.chdir(APP_DIR)

from core.bcc_engine import BCCEngine
from core import llm_client, ai_translate, ai_interpret
import platform as _platform
if _platform.system() == "Windows":
    from core import preprocess_win as preprocess
else:
    from core import preprocess

# vendored 补丁:语料统一放在技能根目录 data/Corpus(与 search.py 共享)
CORPUS_PATH = os.path.join("..", "data", "Corpus")

st.set_page_config(page_title="BCC AI 语料库工具", page_icon="📚", layout="wide")


# ── 缓存引擎(避免每次交互重建索引)──────────────────────────────────
@st.cache_resource
def get_engine():
    return BCCEngine(CORPUS_PATH)


def corpus_ready():
    """Corpus 目录里有没有语料文件。"""
    if not os.path.isdir(CORPUS_PATH):
        return False
    return any(f.endswith(".txt") for f in os.listdir(CORPUS_PATH))


# ── 侧边栏:API key 与状态 ───────────────────────────────────────────
def sidebar():
    st.sidebar.title("📚 BCC AI 语料库")
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔑 API 设置")
    settings = llm_client.load_settings()

    providers = ["openai-compatible", "claude", "aicore"]
    cur_provider = settings.get("provider", "openai-compatible")
    provider_idx = providers.index(cur_provider) if cur_provider in providers else 0
    provider = st.sidebar.selectbox("模型提供方", providers, index=provider_idx,
                                    help="openai-compatible = 硅基流动/阿里百炼/智谱等国内平台；claude = 直连 Anthropic；aicore = SAP AI Core")

    cfg = {"provider": provider}

    if provider == "aicore":
        # 凭证全从 AI/.env 读取，不在前端展示
        cfg["aicore_auth_url"] = os.environ.get("AICORE_AUTH_URL", "")
        cfg["aicore_client_id"] = os.environ.get("AICORE_CLIENT_ID", "")
        cfg["aicore_client_secret"] = os.environ.get("AICORE_CLIENT_SECRET", "")
        cfg["base_url"] = os.environ.get("AICORE_BASE_URL", "")
        cfg["aicore_resource_group"] = os.environ.get("AICORE_RESOURCE_GROUP", "default")
        cfg["api_key"] = ""

        # 模型列表：session_state 缓存，按钮刷新
        if "aicore_models" not in st.session_state:
            st.session_state["aicore_models"] = []
        if st.sidebar.button("🔄 刷新可用模型"):
            try:
                from core.aicore_client import AICoreClient
                _c = AICoreClient(
                    auth_url=cfg["aicore_auth_url"],
                    base_url=cfg["base_url"],
                    client_id=cfg["aicore_client_id"],
                    client_secret=cfg["aicore_client_secret"],
                    resource_group=cfg["aicore_resource_group"],
                )
                st.session_state["aicore_models"] = _c.list_models()
                st.sidebar.success(f"获取到 {len(st.session_state['aicore_models'])} 个模型")
            except Exception as e:
                st.sidebar.error(f"刷新失败: {e}")

        models_list = st.session_state["aicore_models"]
        saved_model = settings.get("model", llm_client.AICORE_DEFAULT_MODEL)
        if models_list:
            idx = models_list.index(saved_model) if saved_model in models_list else 0
            cfg["model"] = st.sidebar.selectbox("模型", models_list, index=idx)
        else:
            cfg["model"] = st.sidebar.text_input(
                "模型名称", value=saved_model,
                help="点击「刷新可用模型」可从 AI Core 拉取列表")
    elif provider == "openai-compatible":
        cfg["api_key"] = st.sidebar.text_input(
            "API Key", value=settings.get("api_key", ""),
            type="password", help="从硅基流动/阿里百炼/智谱等平台获取的 Key，仅存本地")
        cfg["base_url"] = st.sidebar.text_input(
            "Base URL", value=settings.get("base_url", "https://api.siliconflow.cn/v1"),
            help="各平台的 API 地址，如 https://api.siliconflow.cn/v1")
        cfg["model"] = st.sidebar.text_input(
            "模型名", value=settings.get("model", ""),
            placeholder="从平台「模型广场」复制免费模型名",
            help="去平台「模型广场」找标注「免费」的模型，复制名称粘贴到这里")
        cfg["aicore_auth_url"] = ""
        cfg["aicore_client_id"] = ""
        cfg["aicore_client_secret"] = ""
        cfg["aicore_resource_group"] = "default"
    else:
        cfg["api_key"] = st.sidebar.text_input(
            "API Key", value=settings.get("api_key", ""),
            type="password", help="你自己的 Anthropic key,仅存本地")
        cfg["model"] = st.sidebar.text_input(
            "模型", value=settings.get("model", llm_client.DEFAULT_MODEL))
        cfg["base_url"] = st.sidebar.text_input(
            "Base URL(可选,走代理时填)", value=settings.get("base_url", ""),
            help="留空走官方 API;走本地代理时填,如 http://localhost:6655/anthropic")
        cfg["aicore_auth_url"] = ""
        cfg["aicore_client_id"] = ""
        cfg["aicore_client_secret"] = ""
        cfg["aicore_resource_group"] = "default"

    if st.sidebar.button("💾 保存设置"):
        llm_client.save_settings(cfg)
        st.sidebar.success("已保存到本地 config/settings.json")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 语料库状态")
    if corpus_ready():
        files = [f for f in os.listdir(CORPUS_PATH) if f.endswith(".txt")]
        st.sidebar.success(f"已就绪:{len(files)} 个语料文件")
    else:
        st.sidebar.warning("语料库为空,请到「语料管理」导入")
    return cfg


# ── 结果渲染 ─────────────────────────────────────────────────────────
def render_result(result):
    typ = result.get("type", "")
    total = result.get("total", 0)
    if "raw" in result:
        st.error("检索返回无法解析:")
        st.code(str(result["raw"])[:2000])
        return
    st.caption(f"命中总量:{total}")
    records = result.get("records", [])
    if not records:
        st.info("没有命中结果。可换个检索式或确认语料库已建索引。")
        return
    if typ == "Freq":
        df = pd.DataFrame([{"词/结构": r.get("word", ""), "频次": r.get("freq", 0)}
                           for r in records])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ 导出 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "freq.csv", "text/csv")
    elif typ == "Context":
        df = pd.DataFrame([{"左语境": r.get("left", ""), "关键词": r.get("keyword", ""),
                            "右语境": r.get("right", "")} for r in records])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("⬇️ 导出 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "context.csv", "text/csv")
    elif typ == "Count":
        st.metric("命中总数", total)


# ── Tab 1:基础检索 ──────────────────────────────────────────────────
def tab_basic():
    st.header("🔍 基础检索")
    st.markdown("直接输入 BCC 检索式。不熟悉语法?看右侧速查表,或用「AI 分析」标签页。")
    col1, col2 = st.columns([2, 1])
    with col1:
        query = st.text_input("检索式", value="很a", key="basic_query",
                              placeholder="如:a的n、很d、很(~){$1=[经常 常常 偶尔]}")
        mode = st.radio("输出模式", ["上下文", "频率", "计数"], horizontal=True, key="basic_mode")
        num = st.slider("返回条数", 10, 1000, 100, key="basic_num")
        if st.button("检索", type="primary", key="basic_run"):
            if not corpus_ready():
                st.error("语料库为空,请先到「语料管理」导入语料。")
            else:
                eng = get_engine()
                with st.spinner("检索中…"):
                    if mode == "频率":
                        res = eng.search_freq(query, number=num)
                    elif mode == "上下文":
                        res = eng.search_context(query, number=num)
                    else:
                        res = eng.count(query)
                render_result(res)
    with col2:
        with st.expander("📖 检索语法速查", expanded=True):
            root = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(root, "grammar", "bcc_syntax.md")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    st.markdown(f.read())


def _llm_from_cfg(cfg):
    return llm_client.LLMClient(
        api_key=cfg.get("api_key", ""),
        model=cfg.get("model"),
        provider=cfg.get("provider", "claude"),
        base_url=cfg.get("base_url", ""),
        aicore_auth_url=cfg.get("aicore_auth_url", ""),
        aicore_client_id=cfg.get("aicore_client_id", ""),
        aicore_client_secret=cfg.get("aicore_client_secret", ""),
        aicore_resource_group=cfg.get("aicore_resource_group", "default"),
    )


# ── Tab 2:AI 分析(层次 A + B)──────────────────────────────────────
def _do_search(eng, query, mode, num):
    if mode == "频率":
        return eng.search_freq(query, number=num)
    elif mode == "上下文":
        return eng.search_context(query, number=num)
    else:
        return eng.count(query)


def tab_ai(cfg):
    st.header("🤖 AI 分析")
    st.markdown("用**中文**描述你想查什么,AI 帮你生成检索式,再检索,再解读。")

    if not cfg.get("api_key") and cfg.get("provider", "openai-compatible") in ("claude", "openai-compatible"):
        st.warning("请先在左侧填入 API Key 并保存。")
        return
    if cfg.get("provider") == "aicore" and not cfg.get("aicore_client_id"):
        st.warning("请先在左侧填入 AI Core 凭证并保存。")
        return

    question = st.text_area("你的研究问题", key="ai_question",
                            placeholder="例如:分析「才」和「就」跟其他成分的搭配有什么差别")

    # ── ① 生成检索式 ────────────────────────────────────────────────
    if st.button("① 生成检索式", key="ai_gen"):
        with st.spinner("AI 正在分析问题并生成检索式…"):
            try:
                llm = _llm_from_cfg(cfg)
                result = ai_translate.translate(question, llm)
                if isinstance(result, dict) and result.get("mode") == "compare":
                    st.session_state["ai_mode_type"] = "compare"
                    st.session_state["ai_labels"] = result["labels"]
                    st.session_state["ai_query_a"] = result["queries"][0]
                    st.session_state["ai_query_b"] = result["queries"][1]
                    st.session_state["ai_query_a_edit"] = result["queries"][0]
                    st.session_state["ai_query_b_edit"] = result["queries"][1]
                else:
                    st.session_state["ai_mode_type"] = "single"
                    st.session_state["ai_query"] = result
                    st.session_state["ai_query_edit"] = result
                # 清除上一次的检索/解读结果
                for k in ("ai_result", "ai_result_a", "ai_result_b", "ai_analysis"):
                    st.session_state.pop(k, None)
            except Exception as e:
                st.error(f"生成失败:{e}")

    # ── ② 展示检索式 + 检索按钮 ─────────────────────────────────────
    mode_type = st.session_state.get("ai_mode_type")

    if mode_type == "compare":
        labels = st.session_state.get("ai_labels", ["A", "B"])
        st.info("🔀 检测到对比查询,已生成两条检索式")
        col_a, col_b = st.columns(2)
        with col_a:
            edited_a = st.text_input(f"② 检索式 A:【{labels[0]}】(可编辑)",
                                     value=st.session_state.get("ai_query_a", ""),
                                     key="ai_query_a_edit")
        with col_b:
            edited_b = st.text_input(f"② 检索式 B:【{labels[1]}】(可编辑)",
                                     value=st.session_state.get("ai_query_b", ""),
                                     key="ai_query_b_edit")

        mode = st.radio("输出模式", ["上下文", "频率", "计数"],
                        horizontal=True, key="ai_search_mode")
        num = st.slider("返回条数", 10, 1000, 100, key="ai_num")

        if st.button("② 执行对比检索", type="primary", key="ai_run_compare"):
            if not corpus_ready():
                st.error("语料库为空,请先导入语料。")
                return
            eng = get_engine()
            with st.spinner(f"检索「{labels[0]}」…"):
                st.session_state["ai_result_a"] = _do_search(eng, edited_a, mode, num)
            with st.spinner(f"检索「{labels[1]}」…"):
                st.session_state["ai_result_b"] = _do_search(eng, edited_b, mode, num)
            st.session_state.pop("ai_analysis", None)

        if "ai_result_a" in st.session_state and "ai_result_b" in st.session_state:
            st.markdown("---")
            st.subheader("检索结果")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**【{labels[0]}】**")
                render_result(st.session_state["ai_result_a"])
            with col_b:
                st.markdown(f"**【{labels[1]}】**")
                render_result(st.session_state["ai_result_b"])

            st.markdown("---")
            if st.button("③ AI 对比解读", key="ai_interpret_compare"):
                with st.spinner("AI 正在对比分析…"):
                    try:
                        llm = _llm_from_cfg(cfg)
                        analysis = ai_interpret.compare_interpret(
                            st.session_state["ai_result_a"],
                            st.session_state["ai_result_b"],
                            llm,
                            question=question,
                            label_a=labels[0],
                            label_b=labels[1],
                        )
                        st.session_state["ai_analysis"] = analysis
                    except Exception as e:
                        st.error(f"解读失败:{e}")

            if st.session_state.get("ai_analysis"):
                st.subheader("🧠 AI 对比解读")
                st.markdown(st.session_state["ai_analysis"])

    elif mode_type == "single":
        edited = st.text_input("② AI 生成的检索式(可编辑)",
                               value=st.session_state.get("ai_query", ""),
                               key="ai_query_edit")
        mode = st.radio("输出模式", ["上下文", "频率", "计数"],
                        horizontal=True, key="ai_search_mode")
        num = st.slider("返回条数", 10, 1000, 100, key="ai_num")

        if st.button("② 执行检索", type="primary", key="ai_run_single"):
            if not corpus_ready():
                st.error("语料库为空,请先导入语料。")
                return
            eng = get_engine()
            with st.spinner("检索中…"):
                st.session_state["ai_result"] = _do_search(eng, edited, mode, num)
            st.session_state.pop("ai_analysis", None)

        if "ai_result" in st.session_state:
            st.markdown("---")
            st.subheader("检索结果")
            render_result(st.session_state["ai_result"])

            st.markdown("---")
            if st.button("③ AI 解读", key="ai_interpret_single"):
                with st.spinner("AI 正在解读…"):
                    try:
                        llm = _llm_from_cfg(cfg)
                        analysis = ai_interpret.interpret(
                            st.session_state["ai_result"], llm, question=question)
                        st.session_state["ai_analysis"] = analysis
                    except Exception as e:
                        st.error(f"解读失败:{e}")

            if st.session_state.get("ai_analysis"):
                st.subheader("🧠 AI 解读")
                st.markdown(st.session_state["ai_analysis"])


BUILTIN_CORPUS_DIRS = [
    os.path.join(APP_DIR, "corpus-source", "01-main"),
    os.path.join(APP_DIR, "corpus-source", "02-supplementary"),
]


def builtin_corpus_available():
    return any(os.path.isdir(d) for d in BUILTIN_CORPUS_DIRS)


# ── Tab 3:语料管理 ──────────────────────────────────────────────────
def tab_corpus():
    st.header("📁 语料管理")

    st.subheader("当前语料库状态")
    if corpus_ready():
        files = [f for f in os.listdir(CORPUS_PATH) if f.endswith(".txt")]
        st.success(f"✅ 已就绪:{len(files)} 个语料文件")
        with st.expander("查看文件列表"):
            st.table(pd.DataFrame({"语料文件": sorted(files)}))
    else:
        st.warning("语料库为空,请通过下方方式导入。")

    st.markdown("---")

    # ── 内置语料一键导入 ──
    if builtin_corpus_available():
        st.subheader("⚡ 内置语料库(Spoken Chinese Corpus)")
        st.markdown("项目自带语料已就位,点击按钮即可导入(约 3~5 分钟)。")
        if st.button("📥 一键导入内置语料库", key="import_builtin"):
            import subprocess
            script = os.path.join(APP_DIR, "scripts", "import_builtin_corpus.py")
            with st.spinner("正在转换语料,请稍候(可在终端查看进度)…"):
                result = subprocess.run(
                    [sys.executable, script],
                    capture_output=True, text=True, cwd=APP_DIR
                )
            if result.returncode == 0:
                import shutil
                idx = os.path.join(os.path.dirname(CORPUS_PATH), "CorpusIdx")
                if os.path.isdir(idx):
                    shutil.rmtree(idx)
                get_engine.clear()
                st.success("内置语料库导入完成！刷新页面后即可检索。")
                st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
            else:
                st.error("导入出错，请查看终端日志。")
                st.code(result.stderr[-2000:])
        st.markdown("---")

    st.subheader("方式一:导入共享索引(推荐)")
    st.markdown(
        "从师门网盘下载已建好的索引文件夹(通常叫 `CorpusIdx`),"
        f"整个放到:\n\n`{os.path.dirname(CORPUS_PATH)}/`\n\n然后重启本工具即可直接检索,无需重建。")

    st.markdown("---")
    st.subheader("方式二:导入自己的语料(纯文本 / Word / 表格)")
    uploaded = st.file_uploader("上传文件", type=["txt", "doc", "docx", "md", "xlsx"],
                                accept_multiple_files=True)
    if uploaded and st.button("处理并加入语料库", type="primary"):
        os.makedirs(CORPUS_PATH, exist_ok=True)
        tmp_dir = os.path.join(os.path.dirname(CORPUS_PATH), "_upload_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        total = 0
        for uf in uploaded:
            tmp_path = os.path.join(tmp_dir, uf.name)
            with open(tmp_path, "wb") as f:
                f.write(uf.getbuffer())
            try:
                info = preprocess.process_file(tmp_path, CORPUS_PATH)
                total += info["sentences"]
                st.write(f"✅ {uf.name}:{info['sentences']} 句")
            except Exception as e:
                st.error(f"❌ {uf.name}:{e}")
        # 重建索引
        import shutil
        idx = os.path.join(os.path.dirname(CORPUS_PATH), "CorpusIdx")
        if os.path.isdir(idx):
            shutil.rmtree(idx)
        get_engine.clear()  # 清缓存,下次检索重新建索引
        st.success(f"共加入 {total} 句。下次检索会自动重建索引。")


def main():
    cfg = sidebar()
    t1, t2, t3 = st.tabs(["🔍 基础检索", "🤖 AI 分析", "📁 语料管理"])
    with t1:
        tab_basic()
    with t2:
        tab_ai(cfg)
    with t3:
        tab_corpus()


if __name__ == "__main__":
    main()
