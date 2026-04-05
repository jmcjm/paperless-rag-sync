from paperless_rag_sync.models import Document, UserMapping


def test_document_from_paperless_response():
    raw = {
        "id": 42,
        "title": "Faktura VAT FS 186/2025",
        "content": "Treść dokumentu po OCR",
        "correspondent": "F.H.U. OPTIMAK",
        "document_type": "Faktura",
        "tags": ["faktura", "okulary"],
        "owner": 1,
        "created": "2025-10-25",
        "modified": "2026-04-05T12:00:00Z",
        "notes": [
            {"note": "Okulary progresywne dla żony"},
            {"note": "Druga notatka"},
        ],
    }
    doc = Document.from_paperless(raw)
    assert doc.document_id == 42
    assert doc.title == "Faktura VAT FS 186/2025"
    assert doc.content == "Treść dokumentu po OCR"
    assert doc.correspondent == "F.H.U. OPTIMAK"
    assert doc.document_type == "Faktura"
    assert doc.tags == ["faktura", "okulary"]
    assert doc.owner_id == 1
    assert doc.created == "2025-10-25"
    assert doc.modified == "2026-04-05T12:00:00Z"
    assert doc.notes == "Okulary progresywne dla żony\nDruga notatka"


def test_document_from_paperless_response_nullable_fields():
    raw = {
        "id": 1,
        "title": "Untitled",
        "content": "Some text",
        "correspondent": None,
        "document_type": None,
        "tags": [],
        "owner": None,
        "created": "2025-01-01",
        "modified": "2025-01-01T00:00:00Z",
        "notes": [],
    }
    doc = Document.from_paperless(raw)
    assert doc.correspondent is None
    assert doc.document_type is None
    assert doc.tags == []
    assert doc.owner_id is None
    assert doc.notes == ""


def test_document_to_text_file_content():
    raw = {
        "id": 42,
        "title": "Faktura VAT FS 186/2025",
        "content": "Treść dokumentu po OCR",
        "correspondent": "F.H.U. OPTIMAK",
        "document_type": "Faktura",
        "tags": ["faktura", "okulary"],
        "owner": 1,
        "created": "2025-10-25",
        "modified": "2026-04-05T12:00:00Z",
        "notes": [{"note": "Notatka"}],
    }
    doc = Document.from_paperless(raw)
    text = doc.to_text()
    assert "Tytuł: Faktura VAT FS 186/2025" in text
    assert "Typ: Faktura" in text
    assert "Od: F.H.U. OPTIMAK" in text
    assert "Data: 2025-10-25" in text
    assert "Tagi: faktura, okulary" in text
    assert "Notatki: Notatka" in text
    assert "---" in text
    assert "Treść dokumentu po OCR" in text


def test_document_to_text_omits_empty_fields():
    raw = {
        "id": 1,
        "title": "Test",
        "content": "Body",
        "correspondent": None,
        "document_type": None,
        "tags": [],
        "owner": None,
        "created": "2025-01-01",
        "modified": "2025-01-01T00:00:00Z",
        "notes": [],
    }
    doc = Document.from_paperless(raw)
    text = doc.to_text()
    assert "Od:" not in text
    assert "Typ:" not in text
    assert "Tagi:" not in text
    assert "Notatki:" not in text
    assert "Tytuł: Test" in text
    assert "Body" in text


def test_document_filename():
    raw = {
        "id": 42,
        "title": "X",
        "content": "Y",
        "correspondent": None,
        "document_type": None,
        "tags": [],
        "owner": None,
        "created": "2025-01-01",
        "modified": "2025-01-01T00:00:00Z",
        "notes": [],
    }
    doc = Document.from_paperless(raw)
    assert doc.filename == "paperless_42.txt"


def test_user_mapping():
    mapping = UserMapping(
        paperless_user_id=1,
        paperless_username="jmc",
        paperless_email="jmc@example.com",
        openwebui_user_id="uuid-abc-123",
    )
    assert mapping.paperless_user_id == 1
    assert mapping.paperless_username == "jmc"
    assert mapping.paperless_email == "jmc@example.com"
    assert mapping.openwebui_user_id == "uuid-abc-123"
