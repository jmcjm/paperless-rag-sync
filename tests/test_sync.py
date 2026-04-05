import os
import tempfile
from unittest.mock import AsyncMock

import pytest

from paperless_rag_sync.config import Config
from paperless_rag_sync.state import StateDB
from paperless_rag_sync.sync import SyncService


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("PAPERLESS_URL", "http://paperless:8000")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "tok")
    monkeypatch.setenv("OPENWEBUI_URL", "http://openwebui:8080")
    monkeypatch.setenv("OPENWEBUI_API_KEY", "sk-key")
    monkeypatch.setenv("SYNC_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("FULL_SCAN_EVERY_N_CYCLES", "3")
    return Config.from_env()


@pytest.fixture
def state_db(tmp_path):
    db = StateDB(str(tmp_path / "test.db"))
    yield db
    db.close()


@pytest.fixture
def mock_paperless():
    mock = AsyncMock()
    mock.fetch_users.return_value = {
        1: {"email": "jmc@example.com", "username": "jmc"},
        2: {"email": "anna@example.com", "username": "anna"},
    }
    mock.fetch_tags.return_value = {10: "faktura", 11: "okulary"}
    mock.fetch_correspondents.return_value = {20: "F.H.U. OPTIMAK"}
    mock.fetch_document_types.return_value = {30: "Faktura"}
    mock.fetch_documents.return_value = []
    mock.fetch_all_document_ids.return_value = set()
    return mock


@pytest.fixture
def mock_openwebui():
    mock = AsyncMock()
    mock.fetch_users.return_value = {
        "jmc@example.com": "owui-uuid-1",
        "anna@example.com": "owui-uuid-2",
    }
    mock.create_knowledge_base.return_value = "kb-new-uuid"
    mock.upload_file.return_value = "file-new-uuid"
    mock.add_file_to_kb.return_value = None
    mock.remove_file_from_kb.return_value = None
    return mock


@pytest.fixture
def sync_service(config, state_db, mock_paperless, mock_openwebui):
    return SyncService(
        config=config,
        state=state_db,
        paperless=mock_paperless,
        openwebui=mock_openwebui,
    )


@pytest.mark.asyncio
async def test_build_user_mappings(sync_service, mock_paperless, mock_openwebui):
    mappings = await sync_service._build_user_mappings()
    assert len(mappings) == 2
    assert mappings[1].openwebui_user_id == "owui-uuid-1"
    assert mappings[2].openwebui_user_id == "owui-uuid-2"


@pytest.mark.asyncio
async def test_build_user_mappings_skips_unmatched(
    sync_service, mock_paperless, mock_openwebui
):
    mock_openwebui.fetch_users.return_value = {"jmc@example.com": "owui-uuid-1"}
    mappings = await sync_service._build_user_mappings()
    assert len(mappings) == 1
    assert 1 in mappings
    assert 2 not in mappings


@pytest.mark.asyncio
async def test_ensure_knowledge_bases_creates_new(
    sync_service, state_db, mock_openwebui
):
    mappings = await sync_service._build_user_mappings()
    await sync_service._ensure_knowledge_bases(mappings)
    assert mock_openwebui.create_knowledge_base.call_count == 2
    kb1 = state_db.get_knowledge_base(1)
    assert kb1 is not None
    assert kb1["openwebui_kb_id"] == "kb-new-uuid"


@pytest.mark.asyncio
async def test_ensure_knowledge_bases_skips_existing(
    sync_service, state_db, mock_openwebui
):
    state_db.upsert_knowledge_base(1, "kb-existing", "owui-uuid-1")
    mappings = await sync_service._build_user_mappings()
    await sync_service._ensure_knowledge_bases(mappings)
    # Only user 2 should get a new KB
    assert mock_openwebui.create_knowledge_base.call_count == 1


@pytest.mark.asyncio
async def test_sync_new_document(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    state_db.upsert_knowledge_base(1, "kb-1", "owui-uuid-1")
    mock_paperless.fetch_documents.return_value = [
        {
            "id": 42,
            "title": "Test Doc",
            "content": "Body",
            "correspondent": 20,
            "document_type": 30,
            "tags": [10, 11],
            "owner": 1,
            "created": "2025-10-25",
            "modified": "2026-04-05T12:00:00Z",
            "notes": [],
        }
    ]
    mappings = await sync_service._build_user_mappings()
    await sync_service._refresh_lookups()
    result = await sync_service._sync_documents(mappings)
    assert result.new == 1
    assert result.updated == 0
    mock_openwebui.upload_file.assert_called_once()
    mock_openwebui.add_file_to_kb.assert_called_once_with("kb-1", "file-new-uuid")
    doc = state_db.get_document(42)
    assert doc is not None
    assert doc["openwebui_file_id"] == "file-new-uuid"


@pytest.mark.asyncio
async def test_sync_updated_document(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    state_db.upsert_knowledge_base(1, "kb-1", "owui-uuid-1")
    state_db.upsert_document(42, "2026-04-04T00:00:00Z", "file-old", "kb-1")
    mock_paperless.fetch_documents.return_value = [
        {
            "id": 42,
            "title": "Updated Doc",
            "content": "New body",
            "correspondent": None,
            "document_type": None,
            "tags": [],
            "owner": 1,
            "created": "2025-10-25",
            "modified": "2026-04-05T12:00:00Z",
            "notes": [],
        }
    ]
    mappings = await sync_service._build_user_mappings()
    await sync_service._refresh_lookups()
    result = await sync_service._sync_documents(mappings)
    assert result.new == 0
    assert result.updated == 1
    mock_openwebui.remove_file_from_kb.assert_called_once_with("kb-1", "file-old")
    mock_openwebui.upload_file.assert_called_once()
    doc = state_db.get_document(42)
    assert doc["openwebui_file_id"] == "file-new-uuid"
    assert doc["modified"] == "2026-04-05T12:00:00Z"


@pytest.mark.asyncio
async def test_sync_skips_unchanged_document(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    state_db.upsert_knowledge_base(1, "kb-1", "owui-uuid-1")
    state_db.upsert_document(42, "2026-04-05T12:00:00Z", "file-existing", "kb-1")
    mock_paperless.fetch_documents.return_value = [
        {
            "id": 42,
            "title": "Same Doc",
            "content": "Same body",
            "correspondent": None,
            "document_type": None,
            "tags": [],
            "owner": 1,
            "created": "2025-10-25",
            "modified": "2026-04-05T12:00:00Z",
            "notes": [],
        }
    ]
    mappings = await sync_service._build_user_mappings()
    await sync_service._refresh_lookups()
    result = await sync_service._sync_documents(mappings)
    assert result.new == 0
    assert result.updated == 0
    mock_openwebui.upload_file.assert_not_called()


@pytest.mark.asyncio
async def test_sync_skips_document_with_no_owner_mapping(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    mock_openwebui.fetch_users.return_value = {"jmc@example.com": "owui-uuid-1"}
    mock_paperless.fetch_documents.return_value = [
        {
            "id": 99,
            "title": "Orphan",
            "content": "Body",
            "correspondent": None,
            "document_type": None,
            "tags": [],
            "owner": 999,
            "created": "2025-01-01",
            "modified": "2025-01-01T00:00:00Z",
            "notes": [],
        }
    ]
    mappings = await sync_service._build_user_mappings()
    await sync_service._refresh_lookups()
    result = await sync_service._sync_documents(mappings)
    assert result.skipped == 1
    mock_openwebui.upload_file.assert_not_called()


@pytest.mark.asyncio
async def test_deletion_scan(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    state_db.upsert_document(1, "t1", "file-1", "kb-1")
    state_db.upsert_document(2, "t2", "file-2", "kb-1")
    state_db.upsert_document(3, "t3", "file-3", "kb-2")
    # Only doc 1 still exists in Paperless
    mock_paperless.fetch_all_document_ids.return_value = {1}
    deleted = await sync_service._deletion_scan()
    assert deleted == 2
    assert state_db.get_document(1) is not None
    assert state_db.get_document(2) is None
    assert state_db.get_document(3) is None
    assert mock_openwebui.remove_file_from_kb.call_count == 2


@pytest.mark.asyncio
async def test_resolve_document_metadata(sync_service):
    await sync_service._refresh_lookups()
    raw = {
        "id": 42,
        "title": "Test",
        "content": "Body",
        "correspondent": 20,
        "document_type": 30,
        "tags": [10, 11],
        "owner": 1,
        "created": "2025-01-01",
        "modified": "2025-01-01T00:00:00Z",
        "notes": [],
    }
    resolved = sync_service._resolve_metadata(raw)
    assert resolved["correspondent"] == "F.H.U. OPTIMAK"
    assert resolved["document_type"] == "Faktura"
    assert resolved["tags"] == ["faktura", "okulary"]


@pytest.mark.asyncio
async def test_sync_skips_empty_content(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    state_db.upsert_knowledge_base(1, "kb-1", "owui-uuid-1")
    mock_paperless.fetch_documents.return_value = [
        {
            "id": 50,
            "title": "Empty Doc",
            "content": "",
            "correspondent": None,
            "document_type": None,
            "tags": [],
            "owner": 1,
            "created": "2025-01-01",
            "modified": "2025-01-01T00:00:00Z",
            "notes": [],
        }
    ]
    mappings = await sync_service._build_user_mappings()
    await sync_service._refresh_lookups()
    result = await sync_service._sync_documents(mappings)
    assert result.skipped == 1
    mock_openwebui.upload_file.assert_not_called()


@pytest.mark.asyncio
async def test_run_cycle_full(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    mock_paperless.fetch_documents.return_value = [
        {
            "id": 42,
            "title": "Test Doc",
            "content": "Body",
            "correspondent": 20,
            "document_type": 30,
            "tags": [10, 11],
            "owner": 1,
            "created": "2025-10-25",
            "modified": "2026-04-05T12:00:00Z",
            "notes": [],
        }
    ]
    mock_paperless.fetch_all_document_ids.return_value = {42}

    result = await sync_service.run_cycle()
    assert result.new == 1
    assert state_db.get_last_sync_timestamp() is not None
    assert state_db.get_cycle_count() == 1
    # Cycle 0 is a full scan (0 % 3 == 0), so lookups + deletion scan ran
    mock_paperless.fetch_tags.assert_called_once()
    mock_paperless.fetch_all_document_ids.assert_called_once()


@pytest.mark.asyncio
async def test_run_cycle_skips_full_scan_on_non_zero_cycle(
    sync_service, state_db, mock_paperless, mock_openwebui
):
    # Set cycle count to 1 (not divisible by 3 = full_scan_every_n_cycles)
    state_db.increment_cycle_count()
    mock_paperless.fetch_documents.return_value = []

    result = await sync_service.run_cycle()
    assert result.new == 0
    mock_paperless.fetch_tags.assert_not_called()
    mock_paperless.fetch_all_document_ids.assert_not_called()
    assert state_db.get_cycle_count() == 2
