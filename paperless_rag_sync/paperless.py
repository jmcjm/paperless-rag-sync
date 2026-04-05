from __future__ import annotations

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BACKOFF_BASE = 1
BACKOFF_MAX = 60


class PaperlessClient:
    def __init__(self, base_url: str, api_token: str) -> None:
        self._base_url = base_url
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Token {api_token}"},
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

    async def _get_paginated(
        self, path: str, params: dict | None = None
    ) -> list[dict]:
        results = []
        url: str | None = f"{self._base_url}{path}"
        while url:
            resp = await self._request_with_retry("GET", url, params=params)
            data = resp.json()
            results.extend(data.get("results", []))
            url = data.get("next")
            params = None  # next URL already has params
        return results

    async def fetch_users(self) -> dict[int, dict[str, str]]:
        results = await self._get_paginated(
            "/api/users/", params={"page_size": "10000"}
        )
        return {
            u["id"]: {"email": u["email"], "username": u.get("username", "")}
            for u in results
            if u.get("email")
        }

    async def fetch_documents(
        self, modified_after: str | None
    ) -> list[dict]:
        params: dict[str, str] = {
            "fields": "id,title,content,correspondent,document_type,tags,owner,created,modified,notes",
            "page_size": "100",
            "ordering": "-modified",
        }
        if modified_after:
            params["modified__gt"] = modified_after
        return await self._get_paginated("/api/documents/", params=params)

    async def fetch_all_document_ids(self) -> set[int]:
        results = await self._get_paginated(
            "/api/documents/", params={"fields": "id", "page_size": "100000"}
        )
        return {doc["id"] for doc in results}

    async def fetch_tags(self) -> dict[int, str]:
        results = await self._get_paginated(
            "/api/tags/", params={"page_size": "10000"}
        )
        return {t["id"]: t["name"] for t in results}

    async def fetch_correspondents(self) -> dict[int, str]:
        results = await self._get_paginated(
            "/api/correspondents/", params={"page_size": "10000"}
        )
        return {c["id"]: c["name"] for c in results}

    async def fetch_document_types(self) -> dict[int, str]:
        results = await self._get_paginated(
            "/api/document_types/", params={"page_size": "10000"}
        )
        return {d["id"]: d["name"] for d in results}
