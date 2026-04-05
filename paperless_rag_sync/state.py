from __future__ import annotations

import sqlite3


class StateDB:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id INTEGER PRIMARY KEY,
                modified TEXT NOT NULL,
                openwebui_file_id TEXT NOT NULL,
                openwebui_kb_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS knowledge_bases (
                paperless_owner_id INTEGER PRIMARY KEY,
                openwebui_kb_id TEXT NOT NULL,
                openwebui_user_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def get_last_sync_timestamp(self) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM sync_state WHERE key = 'last_sync_timestamp'"
        ).fetchone()
        return row["value"] if row else None

    def set_last_sync_timestamp(self, ts: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO sync_state (key, value) VALUES ('last_sync_timestamp', ?)",
            (ts,),
        )
        self._conn.commit()

    def get_cycle_count(self) -> int:
        row = self._conn.execute(
            "SELECT value FROM sync_state WHERE key = 'cycle_count'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def increment_cycle_count(self) -> None:
        current = self.get_cycle_count()
        self._conn.execute(
            "INSERT OR REPLACE INTO sync_state (key, value) VALUES ('cycle_count', ?)",
            (str(current + 1),),
        )
        self._conn.commit()

    def get_document(self, document_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE document_id = ?", (document_id,)
        ).fetchone()
        return dict(row) if row else None

    def upsert_document(
        self,
        document_id: int,
        modified: str,
        openwebui_file_id: str,
        openwebui_kb_id: str,
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO documents
               (document_id, modified, openwebui_file_id, openwebui_kb_id)
               VALUES (?, ?, ?, ?)""",
            (document_id, modified, openwebui_file_id, openwebui_kb_id),
        )
        self._conn.commit()

    def delete_document(self, document_id: int) -> None:
        self._conn.execute(
            "DELETE FROM documents WHERE document_id = ?", (document_id,)
        )
        self._conn.commit()

    def get_all_document_ids(self) -> set[int]:
        rows = self._conn.execute("SELECT document_id FROM documents").fetchall()
        return {row["document_id"] for row in rows}

    def get_documents_synced_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row["cnt"]

    def get_knowledge_base(self, paperless_owner_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM knowledge_bases WHERE paperless_owner_id = ?",
            (paperless_owner_id,),
        ).fetchone()
        return dict(row) if row else None

    def upsert_knowledge_base(
        self, paperless_owner_id: int, openwebui_kb_id: str, openwebui_user_id: str
    ) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO knowledge_bases
               (paperless_owner_id, openwebui_kb_id, openwebui_user_id)
               VALUES (?, ?, ?)""",
            (paperless_owner_id, openwebui_kb_id, openwebui_user_id),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
