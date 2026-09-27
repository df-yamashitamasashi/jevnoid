from __future__ import annotations

import json
from typing import Any

import httpx

CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"


class CloudflareKVPublisher:
    """Writes the public vitals snapshot to Workers KV, where the Pages Function serves it."""

    def __init__(self, account_id: str, namespace_id: str, api_token: str, key: str = "snapshot", timeout_sec: float = 5.0) -> None:
        self.url = f"{CLOUDFLARE_API}/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key}"
        self.api_token = api_token
        self.timeout = timeout_sec

    def publish(self, snapshot: dict[str, Any]) -> None:
        response = httpx.put(
            self.url,
            headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/octet-stream"},
            content=json.dumps(snapshot, ensure_ascii=False).encode("utf-8"),
            timeout=self.timeout,
        )
        response.raise_for_status()
