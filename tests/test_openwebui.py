import pytest
import httpx
import respx

from paperless_rag_sync.openwebui import OpenWebUIClient


@pytest.fixture
def client():
    return OpenWebUIClient(
        base_url="http://openwebui:8080",
        api_key="sk-test-key",
    )


@respx.mock
@pytest.mark.asyncio
async def test_fetch_users(client):
    respx.get("http://openwebui:8080/api/v1/users/all").mock(
        return_value=httpx.Response(200, json=[
            {"id": "uuid-1", "email": "jmc@example.com", "name": "jmc"},
            {"id": "uuid-2", "email": "anna@example.com", "name": "anna"},
        ])
    )
    users = await client.fetch_users()
    assert users == {"jmc@example.com": "uuid-1", "anna@example.com": "uuid-2"}


@respx.mock
@pytest.mark.asyncio
async def test_create_knowledge_base(client):
    respx.post("http://openwebui:8080/api/v1/knowledge/create").mock(
        return_value=httpx.Response(200, json={
            "id": "kb-uuid-123",
            "name": "Paperless Documents — jmc",
        })
    )
    kb_id = await client.create_knowledge_base(
        name="Paperless Documents — jmc",
        description="Auto-synced from Paperless-ngx",
        user_id="uuid-1",
    )
    assert kb_id == "kb-uuid-123"
    req = respx.calls[0].request
    import json
    body = json.loads(req.content)
    assert body["name"] == "Paperless Documents — jmc"
    assert body["access_grants"] == [
        {"type": "user", "id": "uuid-1", "permission": "read"}
    ]


@respx.mock
@pytest.mark.asyncio
async def test_upload_file(client):
    respx.post("http://openwebui:8080/api/v1/files/").mock(
        return_value=httpx.Response(200, json={"id": "file-uuid-abc"})
    )
    file_id = await client.upload_file("paperless_42.txt", b"file content here")
    assert file_id == "file-uuid-abc"


@respx.mock
@pytest.mark.asyncio
async def test_add_file_to_knowledge_base(client):
    route = respx.post("http://openwebui:8080/api/v1/knowledge/kb-123/file/add").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    await client.add_file_to_kb("kb-123", "file-abc")
    import json
    body = json.loads(route.calls[0].request.content)
    assert body == {"file_id": "file-abc"}


@respx.mock
@pytest.mark.asyncio
async def test_remove_file_from_knowledge_base(client):
    route = respx.post(
        "http://openwebui:8080/api/v1/knowledge/kb-123/file/remove"
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    await client.remove_file_from_kb("kb-123", "file-abc")
    import json
    body = json.loads(route.calls[0].request.content)
    assert body == {"file_id": "file-abc"}


@respx.mock
@pytest.mark.asyncio
async def test_auth_header(client):
    route = respx.get("http://openwebui:8080/api/v1/users/all").mock(
        return_value=httpx.Response(200, json=[])
    )
    await client.fetch_users()
    assert route.calls[0].request.headers["Authorization"] == "Bearer sk-test-key"
