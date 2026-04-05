import asyncio
import json
from unittest.mock import MagicMock

import pytest

from paperless_rag_sync.health import HealthServer


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.get_last_sync_timestamp.return_value = "2026-04-05T12:00:00Z"
    state.get_documents_synced_count.return_value = 42
    return state


@pytest.fixture
def health_server(mock_state):
    return HealthServer(state=mock_state, port=0)  # port 0 = random free port


@pytest.mark.asyncio
async def test_health_endpoint(health_server):
    await health_server.start()
    try:
        port = health_server.port
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:{port}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["last_sync"] == "2026-04-05T12:00:00Z"
        assert data["documents_synced"] == 42
    finally:
        await health_server.stop()


@pytest.mark.asyncio
async def test_health_endpoint_no_sync_yet(health_server, mock_state):
    mock_state.get_last_sync_timestamp.return_value = None
    mock_state.get_documents_synced_count.return_value = 0
    await health_server.start()
    try:
        port = health_server.port
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:{port}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["last_sync"] is None
        assert data["documents_synced"] == 0
    finally:
        await health_server.stop()


@pytest.mark.asyncio
async def test_health_404_on_other_paths(health_server):
    await health_server.start()
    try:
        port = health_server.port
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:{port}/other")
        assert resp.status_code == 404
    finally:
        await health_server.stop()
