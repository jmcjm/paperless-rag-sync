from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from paperless_rag_sync.config import Config
from paperless_rag_sync.models import Document, UserMapping
from paperless_rag_sync.state import StateDB
from paperless_rag_sync.paperless import PaperlessClient
from paperless_rag_sync.openwebui import OpenWebUIClient

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    new: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    deleted: int = 0


class SyncService:
    def __init__(
        self,
        config: Config,
        state: StateDB,
        paperless: PaperlessClient,
        openwebui: OpenWebUIClient,
    ) -> None:
        self._config = config
        self._state = state
        self._paperless = paperless
        self._openwebui = openwebui
        self._tags: dict[int, str] = {}
        self._correspondents: dict[int, str] = {}
        self._document_types: dict[int, str] = {}

    async def _build_user_mappings(self) -> dict[int, UserMapping]:
        paperless_users = await self._paperless.fetch_users()
        openwebui_users = await self._openwebui.fetch_users()
        mappings: dict[int, UserMapping] = {}
        for uid, info in paperless_users.items():
            email = info["email"]
            username = info["username"]
            owui_id = openwebui_users.get(email)
            if owui_id:
                mappings[uid] = UserMapping(
                    paperless_user_id=uid,
                    paperless_username=username,
                    paperless_email=email,
                    openwebui_user_id=owui_id,
                )
            else:
                logger.warning("No OpenWebUI user for Paperless user %d (%s)", uid, email)
        return mappings

    async def _ensure_knowledge_bases(
        self, mappings: dict[int, UserMapping]
    ) -> None:
        for uid, mapping in mappings.items():
            existing = self._state.get_knowledge_base(uid)
            if existing:
                continue
            kb_id = await self._openwebui.create_knowledge_base(
                name=f"Paperless Documents — {mapping.paperless_username}",
                description="Auto-synced from Paperless-ngx",
                user_id=mapping.openwebui_user_id,
            )
            self._state.upsert_knowledge_base(uid, kb_id, mapping.openwebui_user_id)
            logger.info("Created KB %s for user %s", kb_id, mapping.paperless_email)

    async def _refresh_lookups(self) -> None:
        self._tags = await self._paperless.fetch_tags()
        self._correspondents = await self._paperless.fetch_correspondents()
        self._document_types = await self._paperless.fetch_document_types()

    def _resolve_metadata(self, raw: dict) -> dict:
        resolved = dict(raw)
        corr_id = raw.get("correspondent")
        resolved["correspondent"] = self._correspondents.get(corr_id) if corr_id else None
        dtype_id = raw.get("document_type")
        resolved["document_type"] = self._document_types.get(dtype_id) if dtype_id else None
        tag_ids = raw.get("tags") or []
        resolved["tags"] = [self._tags[t] for t in tag_ids if t in self._tags]
        return resolved

    async def _sync_documents(
        self, mappings: dict[int, UserMapping]
    ) -> SyncResult:
        result = SyncResult()
        last_sync = self._state.get_last_sync_timestamp()
        raw_docs = await self._paperless.fetch_documents(modified_after=last_sync)

        for raw in raw_docs:
            doc_id = raw["id"]
            owner_id = raw.get("owner")

            if owner_id not in mappings:
                logger.warning(
                    "Skipping doc %d (%s): no user mapping for owner %s",
                    doc_id, raw.get("title", "?"), owner_id,
                )
                result.skipped += 1
                continue

            kb_info = self._state.get_knowledge_base(owner_id)
            if not kb_info:
                logger.warning("Skipping doc %d: no KB for owner %d", doc_id, owner_id)
                result.skipped += 1
                continue
            kb_id = kb_info["openwebui_kb_id"]

            if not raw.get("content", "").strip():
                logger.warning("Skipping doc %d (%s): empty content", doc_id, raw.get("title", "?"))
                result.skipped += 1
                continue

            existing = self._state.get_document(doc_id)
            if existing and existing["modified"] == raw["modified"]:
                result.skipped += 1
                continue

            try:
                resolved = self._resolve_metadata(raw)
                doc = Document.from_paperless(resolved)

                if existing:
                    await self._openwebui.remove_file_from_kb(
                        existing["openwebui_kb_id"], existing["openwebui_file_id"]
                    )
                    result.updated += 1
                else:
                    result.new += 1

                file_id = await self._openwebui.upload_file(
                    doc.filename, doc.to_text().encode("utf-8")
                )
                await self._openwebui.add_file_to_kb(kb_id, file_id)
                self._state.upsert_document(doc_id, raw["modified"], file_id, kb_id)
                logger.info(
                    "Synced document %d \"%s\" (%s)",
                    doc_id, doc.title, "updated" if existing else "new",
                )
            except Exception:
                logger.exception("Failed to sync document %d", doc_id)
                result.errors += 1

        return result

    async def _deletion_scan(self) -> int:
        paperless_ids = await self._paperless.fetch_all_document_ids()
        known_ids = self._state.get_all_document_ids()
        deleted_ids = known_ids - paperless_ids
        for doc_id in deleted_ids:
            doc = self._state.get_document(doc_id)
            if doc:
                try:
                    await self._openwebui.remove_file_from_kb(
                        doc["openwebui_kb_id"], doc["openwebui_file_id"]
                    )
                except Exception:
                    logger.exception("Failed to remove file for deleted doc %d", doc_id)
                self._state.delete_document(doc_id)
                logger.info("Deleted document %d from OpenWebUI", doc_id)
        return len(deleted_ids)

    async def run_cycle(self) -> SyncResult:
        mappings = await self._build_user_mappings()
        if not mappings:
            logger.warning("No user mappings found — nothing to sync")
            return SyncResult()

        await self._ensure_knowledge_bases(mappings)

        cycle = self._state.get_cycle_count()
        is_full_scan = cycle % self._config.full_scan_every_n_cycles == 0

        if is_full_scan:
            await self._refresh_lookups()

        result = await self._sync_documents(mappings)

        if is_full_scan:
            result.deleted = await self._deletion_scan()

        self._state.set_last_sync_timestamp(
            datetime.now(timezone.utc).isoformat()
        )
        self._state.increment_cycle_count()

        logger.info(
            "Sync cycle %d: %d new, %d updated, %d deleted, %d skipped, %d errors",
            cycle, result.new, result.updated, result.deleted, result.skipped, result.errors,
        )
        return result
