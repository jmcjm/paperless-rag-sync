from __future__ import annotations

import asyncio
import logging
import signal
import sys

from paperless_rag_sync.config import Config
from paperless_rag_sync.health import HealthServer
from paperless_rag_sync.openwebui import OpenWebUIClient
from paperless_rag_sync.paperless import PaperlessClient
from paperless_rag_sync.state import StateDB
from paperless_rag_sync.sync import SyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def run() -> None:
    config = Config.from_env()
    state = StateDB(config.db_path)
    paperless = PaperlessClient(config.paperless_url, config.paperless_api_token)
    openwebui = OpenWebUIClient(config.openwebui_url, config.openwebui_api_key)
    sync_service = SyncService(config, state, paperless, openwebui)
    health = HealthServer(state=state, port=8090)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    await health.start()
    logger.info("Health server started on :8090")
    logger.info(
        "Starting sync loop (interval=%ds, full scan every %d cycles)",
        config.sync_interval_seconds,
        config.full_scan_every_n_cycles,
    )

    try:
        while not stop_event.is_set():
            try:
                result = await sync_service.run_cycle()
                health.set_last_error(None)
            except Exception as e:
                logger.exception("Sync cycle failed")
                health.set_last_error(str(e))
            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=config.sync_interval_seconds
                )
            except asyncio.TimeoutError:
                pass
    finally:
        logger.info("Shutting down...")
        await health.stop()
        await paperless.close()
        await openwebui.close()
        state.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
