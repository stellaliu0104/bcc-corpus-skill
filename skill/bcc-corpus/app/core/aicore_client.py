# -*- coding: utf-8 -*-
"""SAP AI Core 客户端。

流程:
  1. 用 client_id + client_secret 向 AICORE_AUTH_URL 做 Basic Auth 换 Bearer token
  2. 向 AICORE_BASE_URL/lm/deployments 查找 orchestration service 的 deploymentId
  3. 用该 deploymentId 调用 /inference/deployments/{id}/completion
"""

import os
import requests


class AICoreClient:
    def __init__(self, auth_url, base_url, client_id, client_secret, resource_group="default"):
        self._auth_url = auth_url.rstrip("/")
        self._base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._resource_group = resource_group
        self._token = None
        self._deployment_id = None

    # ── OAuth token ──────────────────────────────────────────────────

    def _fetch_token(self):
        resp = requests.post(
            f"{self._auth_url}/oauth/token",
            params={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
            timeout=15,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    @property
    def token(self):
        if not self._token:
            self._fetch_token()
        return self._token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "AI-Resource-Group": self._resource_group,
            "Content-Type": "application/json",
        }

    # ── Deployment discovery ─────────────────────────────────────────

    def _get_deployments(self, status="RUNNING"):
        resp = requests.get(
            f"{self._base_url}/lm/deployments",
            headers=self._headers(),
            params={"status": status},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("resources", [])

    def _find_orchestration_deployment(self):
        """找 scenarioId=orchestration 且 status=RUNNING 的 deploymentId。"""
        deployments = self._get_deployments()
        for d in deployments:
            if d.get("scenarioId") == "orchestration":
                return d["id"]
        raise RuntimeError(
            "未找到运行中的 orchestration deployment。"
            f"当前 RUNNING deployments: {[d.get('id') for d in deployments]}"
        )

    def list_models(self):
        """返回所有 RUNNING foundation-models deployment 的模型名列表(去重、排序)。"""
        deployments = self._get_deployments()
        models = set()
        for d in deployments:
            if d.get("scenarioId") == "foundation-models":
                try:
                    name = d["details"]["resources"]["backendDetails"]["model"]["name"]
                    models.add(name)
                except (KeyError, TypeError):
                    pass
        return sorted(models)

    @property
    def deployment_id(self):
        if not self._deployment_id:
            self._deployment_id = self._find_orchestration_deployment()
        return self._deployment_id

    # ── Inference ────────────────────────────────────────────────────

    def chat(self, system: str, user: str, model: str, max_tokens: int = 2000, temperature: float = 0.0) -> str:
        """单轮对话,返回纯文本回复。"""
        # Claude via AI Core only supports temperature=1; omit to use default
        model_params = {"max_tokens": max_tokens}
        payload = {
            "orchestration_config": {
                "module_configurations": {
                    "llm_module_config": {
                        "model_name": model,
                        "model_params": model_params,
                    },
                    "templating_module_config": {
                        "template": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ]
                    },
                }
            },
        }
        resp = requests.post(
            f"{self._base_url}/inference/deployments/{self.deployment_id}/completion",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["orchestration_result"]["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            import json
            return json.dumps(data, ensure_ascii=False)

    def refresh_token(self):
        """强制刷新 token(token 过期时调用)。"""
        self._token = None
        return self._fetch_token()


# ── 便捷工厂,从环境变量或传参建立客户端 ──────────────────────────────

def client_from_env(
    auth_url=None,
    base_url=None,
    client_id=None,
    client_secret=None,
    resource_group=None,
):
    return AICoreClient(
        auth_url=auth_url or os.environ.get("AICORE_AUTH_URL", ""),
        base_url=base_url or os.environ.get("AICORE_BASE_URL", ""),
        client_id=client_id or os.environ.get("AICORE_CLIENT_ID", ""),
        client_secret=client_secret or os.environ.get("AICORE_CLIENT_SECRET", ""),
        resource_group=resource_group or os.environ.get("AICORE_RESOURCE_GROUP", "default"),
    )
