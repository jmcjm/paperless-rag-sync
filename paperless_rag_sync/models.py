from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    document_id: int
    title: str
    content: str
    correspondent: str | None
    document_type: str | None
    tags: list[str]
    owner_id: int | None
    created: str
    modified: str
    notes: str

    @classmethod
    def from_paperless(cls, raw: dict) -> Document:
        notes_list = raw.get("notes") or []
        notes_text = "\n".join(n["note"] for n in notes_list if n.get("note"))
        return cls(
            document_id=raw["id"],
            title=raw["title"],
            content=raw.get("content") or "",
            correspondent=raw.get("correspondent"),
            document_type=raw.get("document_type"),
            tags=raw.get("tags") or [],
            owner_id=raw.get("owner"),
            created=raw.get("created") or "",
            modified=raw["modified"],
            notes=notes_text,
        )

    def to_text(self) -> str:
        lines = []
        lines.append(f"Tytuł: {self.title}")
        if self.document_type:
            lines.append(f"Typ: {self.document_type}")
        if self.correspondent:
            lines.append(f"Od: {self.correspondent}")
        if self.created:
            lines.append(f"Data: {self.created}")
        if self.tags:
            lines.append(f"Tagi: {', '.join(self.tags)}")
        if self.notes:
            lines.append(f"Notatki: {self.notes}")
        lines.append("---")
        lines.append(self.content)
        return "\n".join(lines)

    @property
    def filename(self) -> str:
        return f"paperless_{self.document_id}.txt"


@dataclass(frozen=True)
class UserMapping:
    paperless_user_id: int
    paperless_username: str
    paperless_email: str
    openwebui_user_id: str
