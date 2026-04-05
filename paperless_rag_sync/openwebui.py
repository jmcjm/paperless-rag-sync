from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BACKOFF_BASE = 1
BACKOFF_MAX = 60


class OpenWebUIClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request_with_retry(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = min(BACKOFF_BASE * (2 ** attempt), BACKOFF_MAX)
                logger.warning(
                    "Request %s %s failed (attempt %d/%d): %s. Retrying in %ds",
                    method, url, attempt + 1, MAX_RETRIES, e, delay,
                )
                await asyncio.sleep(delay)
        raise RuntimeError("unreachable")

    async def fetch_users(self) -> dict[str, str]:
        resp = await self._request_with_retry(
            "GET", f"{self._base_url}/api/v1/users/all"
        )
        users = resp.json()
        return {u["email"]: u["id"] for u in users if u.get("email")}

    async def create_knowledge_base(
        self, name: str, description: str, user_id: str
    ) -> str:
        body = {
            "name": name,
            "description": description,
            "access_grants": [
                {"type": "user", "id": user_id, "permission": "read"}
            ],
        }
        resp = await self._request_with_retry(
            "POST", f"{self._base_url}/api/v1/knowledge/create", json=body
        )
        return resp.json()["id"]

    async def upload_file(self, filename: str, content: bytes) -> str:
        resp = await self._request_with_retry(
            "POST",
            f"{self._base_url}/api/v1/files/",
            files={"file": (filename, content, "text/plain")},
        )
        return resp.json()["id"]

    async def add_file_to_kb(self, kb_id: str, file_id: str) -> None:
        await self._request_with_retry(
            "POST",
            f"{self._base_url}/api/v1/knowledge/{kb_id}/file/add",
            json={"file_id": file_id},
        )

    async def remove_file_from_kb(self, kb_id: str, file_id: str) -> None:
        await self._request_with_retry(
            "POST",
            f"{self._base_url}/api/v1/knowledge/{kb_id}/file/remove",
            json={"file_id": file_id},
            params={"delete_file": "true"},
        )
