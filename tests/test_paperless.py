import pytest
import httpx
import respx

from paperless_rag_sync.paperless import PaperlessClient


@pytest.fixture
def client():
    return PaperlessClient(
        base_url="http://paperless:8000",
        api_token="test-token",
    )


@respx.mock
@pytest.mark.asyncio
async def test_fetch_users(client):
    respx.get("http://paperless:8000/api/users/").mock(
        return_value=httpx.Response(200, json={
            "count": 2,
            "next": None,
            "results": [
                {"id": 1, "username": "jmc", "email": "jmc@example.com"},
                {"id": 2, "username": "anna", "email": "anna@example.com"},
            ],
        })
    )
    users = await client.fetch_users()
    assert users == {
        1: {"email": "jmc@example.com", "username": "jmc"},
        2: {"email": "anna@example.com", "username": "anna"},
    }


@respx.mock
@pytest.mark.asyncio
async def test_fetch_users_skips_empty_email(client):
    respx.get("http://paperless:8000/api/users/").mock(
        return_value=httpx.Response(200, json={
            "count": 1,
            "next": None,
            "results": [
                {"id": 1, "username": "jmc", "email": ""},
            ],
        })
    )
    users = await client.fetch_users()
    assert users == {}


@respx.mock
@pytest.mark.asyncio
async def test_fetch_documents_incremental(client):
    respx.get("http://paperless:8000/api/documents/").mock(
        return_value=httpx.Response(200, json={
            "count": 1,
            "next": None,
            "results": [
                {
                    "id": 42,
                    "title": "Test Doc",
                    "content": "Body text",
                    "correspondent": 1,
                    "document_type": 2,
                    "tags": [3, 4],
                    "owner": 1,
                    "created": "2025-10-25",
                    "modified": "2026-04-05T12:00:00Z",
                    "notes": [],
                }
            ],
        })
    )
    docs = await client.fetch_documents(modified_after="2026-04-01T00:00:00Z")
    assert len(docs) == 1
    assert docs[0]["id"] == 42


@respx.mock
@pytest.mark.asyncio
async def test_fetch_documents_all(client):
    respx.get("http://paperless:8000/api/documents/").mock(
        return_value=httpx.Response(200, json={
            "count": 1,
            "next": None,
            "results": [
                {
                    "id": 1,
                    "title": "Doc",
                    "content": "Body",
                    "correspondent": None,
                    "document_type": None,
                    "tags": [],
                    "owner": 1,
                    "created": "2025-01-01",
                    "modified": "2025-01-01T00:00:00Z",
                    "notes": [],
                }
            ],
        })
    )
    docs = await client.fetch_documents(modified_after=None)
    assert len(docs) == 1


@respx.mock
@pytest.mark.asyncio
async def test_fetch_documents_paginates(client):
    respx.get("http://paperless:8000/api/documents/").mock(
        side_effect=[
            httpx.Response(200, json={
                "count": 2,
                "next": "http://paperless:8000/api/documents/?page=2",
                "results": [{"id": 1, "title": "A", "content": "", "correspondent": None, "document_type": None, "tags": [], "owner": 1, "created": "2025-01-01", "modified": "2025-01-01T00:00:00Z", "notes": []}],
            }),
            httpx.Response(200, json={
                "count": 2,
                "next": None,
                "results": [{"id": 2, "title": "B", "content": "", "correspondent": None, "document_type": None, "tags": [], "owner": 1, "created": "2025-01-01", "modified": "2025-01-01T00:00:00Z", "notes": []}],
            }),
        ]
    )
    docs = await client.fetch_documents(modified_after=None)
    assert len(docs) == 2
    assert docs[0]["id"] == 1
    assert docs[1]["id"] == 2


@respx.mock
@pytest.mark.asyncio
async def test_fetch_all_document_ids(client):
    respx.get("http://paperless:8000/api/documents/").mock(
        return_value=httpx.Response(200, json={
            "count": 3,
            "next": None,
            "results": [
                {"id": 10},
                {"id": 20},
                {"id": 30},
            ],
        })
    )
    ids = await client.fetch_all_document_ids()
    assert ids == {10, 20, 30}


@respx.mock
@pytest.mark.asyncio
async def test_fetch_tags(client):
    respx.get("http://paperless:8000/api/tags/").mock(
        return_value=httpx.Response(200, json={
            "count": 2,
            "next": None,
            "results": [
                {"id": 1, "name": "faktura"},
                {"id": 2, "name": "okulary"},
            ],
        })
    )
    tags = await client.fetch_tags()
    assert tags == {1: "faktura", 2: "okulary"}


@respx.mock
@pytest.mark.asyncio
async def test_fetch_correspondents(client):
    respx.get("http://paperless:8000/api/correspondents/").mock(
        return_value=httpx.Response(200, json={
            "count": 1,
            "next": None,
            "results": [{"id": 1, "name": "F.H.U. OPTIMAK"}],
        })
    )
    corrs = await client.fetch_correspondents()
    assert corrs == {1: "F.H.U. OPTIMAK"}


@respx.mock
@pytest.mark.asyncio
async def test_fetch_document_types(client):
    respx.get("http://paperless:8000/api/document_types/").mock(
        return_value=httpx.Response(200, json={
            "count": 1,
            "next": None,
            "results": [{"id": 1, "name": "Faktura"}],
        })
    )
    types = await client.fetch_document_types()
    assert types == {1: "Faktura"}


@respx.mock
@pytest.mark.asyncio
async def test_auth_header(client):
    route = respx.get("http://paperless:8000/api/users/").mock(
        return_value=httpx.Response(200, json={"count": 0, "next": None, "results": []})
    )
    await client.fetch_users()
    assert route.calls[0].request.headers["Authorization"] == "Token test-token"
