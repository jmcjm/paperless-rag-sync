from __future__ import annotations

import asyncio
import json
from asyncio import StreamReader, StreamWriter

from paperless_rag_sync.state import StateDB


class HealthServer:
    def __init__(self, state: StateDB, port: int = 8090) -> None:
        self._state = state
        self._requested_port = port
        self._server: asyncio.Server | None = None
        self._last_error: str | None = None
        self.port: int = port

    def set_last_error(self, error: str | None) -> None:
        self._last_error = error

    async def _handle(self, reader: StreamReader, writer: StreamWriter) -> None:
        data = await reader.read(4096)
        request_line = data.split(b"\r\n")[0].decode()
        path = request_line.split(" ")[1] if " " in request_line else "/"

        if path == "/health":
            body = json.dumps({
                "status": "ok",
                "last_sync": self._state.get_last_sync_timestamp(),
                "documents_synced": self._state.get_documents_synced_count(),
                "last_error": self._last_error,
            })
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"\r\n"
                f"{body}"
            )
        else:
            body = "Not Found"
            response = (
                f"HTTP/1.1 404 Not Found\r\n"
                f"Content-Length: {len(body)}\r\n"
                f"\r\n"
                f"{body}"
            )

        writer.write(response.encode())
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle, "0.0.0.0", self._requested_port
        )
        sock = self._server.sockets[0]
        self.port = sock.getsockname()[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
