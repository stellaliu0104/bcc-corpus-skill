# -*- coding: utf-8 -*-
"""LLM 接口抽象层。

支持四种 provider:
  claude            — 直连 Anthropic API
  deepseek / glm    — 官方 OpenAI Chat Completions 兼容接口
  openai-compatible — 任意兼容 OpenAI Chat Completions 的接口
统一提供 chat() 方法;阶段二的 agent 用 chat_with_tools() 走 tool-use 循环。
"""

import os
import json


DEFAULT_MODEL = "claude-opus-4-8"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"
GLM_DEFAULT_MODEL = "glm-5.3"
OPENAI_COMPAT_DEFAULT_MODEL = ""

# 启动时尝试加载 AI/.env(开发机便捷配置,分发包里不存在则忽略)
def _load_dotenv():
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "AI", ".env")
        if os.path.isfile(env_path):
            load_dotenv(env_path, override=False)
    except ImportError:
        pass

_load_dotenv()


class LLMClient:
    """LLM 客户端封装。支持 Claude 及 OpenAI Chat Completions 兼容接口。"""

    def __init__(self, api_key=None, model=None, provider="claude", base_url=""):
        self.provider = provider
        provider_defaults = {
            "deepseek": ("https://api.deepseek.com", DEEPSEEK_DEFAULT_MODEL, "DEEPSEEK_API_KEY"),
            "glm": ("https://open.bigmodel.cn/api/paas/v4/", GLM_DEFAULT_MODEL, "ZAI_API_KEY"),
            "openai-compatible": ("", OPENAI_COMPAT_DEFAULT_MODEL, "OPENAI_API_KEY"),
        }

        if provider in provider_defaults:
            default_url, default_model, env_key = provider_defaults[provider]
            self.base_url = base_url or default_url
            self.model = model or default_model
            self.api_key = api_key or os.environ.get(env_key, "")
        else:
            self.base_url = base_url
            self.model = model or DEFAULT_MODEL
            self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

        self._client = None

    @property
    def client(self):
        if self._client is None:
            if self.provider == "claude":
                from anthropic import Anthropic
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = Anthropic(**kwargs)
            elif self.provider in ("deepseek", "glm", "openai-compatible"):
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            else:
                raise NotImplementedError(f"暂未实现 provider={self.provider}")
        return self._client

    def chat(self, system, user, max_tokens=2000, temperature=0.0):
        """单轮对话,返回纯文本。"""
        if self.provider == "claude":
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in resp.content if b.type == "text")
        if self.provider in ("deepseek", "glm", "openai-compatible"):
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return resp.choices[0].message.content or ""
        raise NotImplementedError

    def chat_with_tools(self, system, messages, tools, max_tokens=2000):
        """带工具的一次调用(阶段二 agent 用)。返回原始 response 对象。"""
        if self.provider == "claude":
            return self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=tools,
            )
        raise NotImplementedError(f"chat_with_tools 暂不支持 provider={self.provider}")


# ── 配置读写 ─────────────────────────────────────────────────────────

def _config_path():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "config", "settings.json")


def load_settings():
    """读取用户本地配置(不存在则返回默认)。"""
    path = _config_path()
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "provider": "deepseek",
        "api_key": "",
        "model": DEEPSEEK_DEFAULT_MODEL,
        "base_url": "https://api.deepseek.com",
    }


def save_settings(settings):
    """把配置写入本地 config/settings.json(含 API key,不进代码库)。"""
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def client_from_settings():
    s = load_settings()
    provider = s.get("provider", "deepseek")
    return LLMClient(
        api_key=s.get("api_key"),
        model=s.get("model"),
        provider=provider,
        base_url=s.get("base_url", ""),
    )
