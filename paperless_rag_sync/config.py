from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    paperless_url: str
    paperless_api_token: str
    openwebui_url: str
    openwebui_api_key: str
    sync_interval_seconds: int = 60
    full_scan_every_n_cycles: int = 10
    db_path: str = "/app/data/sync.db"

    @classmethod
    def from_env(cls) -> Config:
        def required(name: str) -> str:
            val = os.environ.get(name)
            if not val:
                raise ValueError(f"Missing required environment variable: {name}")
            return val

        return cls(
            paperless_url=required("PAPERLESS_URL").rstrip("/"),
            paperless_api_token=required("PAPERLESS_API_TOKEN"),
            openwebui_url=required("OPENWEBUI_URL").rstrip("/"),
            openwebui_api_key=required("OPENWEBUI_API_KEY"),
            sync_interval_seconds=int(os.environ.get("SYNC_INTERVAL_SECONDS", "60")),
            full_scan_every_n_cycles=int(os.environ.get("FULL_SCAN_EVERY_N_CYCLES", "10")),
            db_path=os.environ.get("DB_PATH", "/app/data/sync.db"),
        )
