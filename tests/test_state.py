from paperless_rag_sync.state import StateDB


def test_init_creates_tables(db):
    cursor = db._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "documents" in tables
    assert "knowledge_bases" in tables
    assert "sync_state" in tables


def test_get_set_sync_state(db):
    assert db.get_last_sync_timestamp() is None
    db.set_last_sync_timestamp("2026-04-05T12:00:00Z")
    assert db.get_last_sync_timestamp() == "2026-04-05T12:00:00Z"


def test_get_set_cycle_count(db):
    assert db.get_cycle_count() == 0
    db.increment_cycle_count()
    assert db.get_cycle_count() == 1
    db.increment_cycle_count()
    assert db.get_cycle_count() == 2


def test_upsert_and_get_document(db):
    db.upsert_document(42, "2026-04-05T12:00:00Z", "file-abc", "kb-xyz")
    doc = db.get_document(42)
    assert doc is not None
    assert doc["modified"] == "2026-04-05T12:00:00Z"
    assert doc["openwebui_file_id"] == "file-abc"
    assert doc["openwebui_kb_id"] == "kb-xyz"


def test_upsert_document_overwrites(db):
    db.upsert_document(42, "2026-04-05T12:00:00Z", "file-abc", "kb-xyz")
    db.upsert_document(42, "2026-04-06T12:00:00Z", "file-def", "kb-xyz")
    doc = db.get_document(42)
    assert doc["modified"] == "2026-04-06T12:00:00Z"
    assert doc["openwebui_file_id"] == "file-def"


def test_delete_document(db):
    db.upsert_document(42, "2026-04-05T12:00:00Z", "file-abc", "kb-xyz")
    db.delete_document(42)
    assert db.get_document(42) is None


def test_get_all_document_ids(db):
    db.upsert_document(1, "t1", "f1", "kb1")
    db.upsert_document(2, "t2", "f2", "kb1")
    db.upsert_document(3, "t3", "f3", "kb2")
    assert db.get_all_document_ids() == {1, 2, 3}


def test_upsert_and_get_knowledge_base(db):
    db.upsert_knowledge_base(1, "kb-abc", "user-xyz")
    kb = db.get_knowledge_base(1)
    assert kb is not None
    assert kb["openwebui_kb_id"] == "kb-abc"
    assert kb["openwebui_user_id"] == "user-xyz"


def test_get_knowledge_base_missing(db):
    assert db.get_knowledge_base(999) is None


def test_get_document_missing(db):
    assert db.get_document(999) is None


def test_documents_synced_count(db):
    assert db.get_documents_synced_count() == 0
    db.upsert_document(1, "t1", "f1", "kb1")
    db.upsert_document(2, "t2", "f2", "kb1")
    assert db.get_documents_synced_count() == 2
