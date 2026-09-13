"""WebSocket fanout for live incident / health / prediction push."""
from __future__ import annotations

import asyncio
from collections import defaultdict


class Manager:
    def __init__(self):
        self.rooms = defaultdict(list)
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, session_id: int, ws):
        await ws.accept()
        self.loop = asyncio.get_running_loop()
        self.rooms[session_id].append(ws)

    def disconnect(self, session_id: int, ws):
        if ws in self.rooms[session_id]:
            self.rooms[session_id].remove(ws)

    async def broadcast(self, session_id: int, message: dict):
        dead = []
        for ws in self.rooms[session_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    def broadcast_threadsafe(self, session_id: int, message: dict):
        """For background jobs running outside the event loop."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(session_id, message), self.loop)


manager = Manager()
