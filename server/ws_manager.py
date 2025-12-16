# server/ws_manager.py

from typing import Dict, Set
from fastapi import WebSocket
import asyncio


class WSManager:
    """
    Simple WebSocket manager that keeps track of text/audio clients
    per target language (e.g. 'de', 'fr', ...).
    """

    def __init__(self) -> None:
        # language -> set of WebSocket connections
        self.text_clients: Dict[str, Set[WebSocket]] = {}
        self.audio_clients: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    # -------- TEXT --------
    async def connect_text(self, lang: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.text_clients.setdefault(lang, set()).add(ws)

    async def disconnect_text(self, lang: str, ws: WebSocket) -> None:
        async with self._lock:
            if lang in self.text_clients:
                self.text_clients[lang].discard(ws)

    async def broadcast_text(self, lang: str, message: dict) -> None:
        """
        Send JSON message to all text clients in a given language room.

        message example:
        {
            "segment": "Übersetzter Satz...",
            "source": "Original sentence",
            "lang": "de",
            "ts": 1234567890.0
        }
        """
        async with self._lock:
            clients = list(self.text_clients.get(lang, set()))

        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        # remove dead connections
        for ws in dead:
            await self.disconnect_text(lang, ws)

    # -------- AUDIO --------
    async def connect_audio(self, lang: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.audio_clients.setdefault(lang, set()).add(ws)

    async def disconnect_audio(self, lang: str, ws: WebSocket) -> None:
        async with self._lock:
            if lang in self.audio_clients:
                self.audio_clients[lang].discard(ws)

    async def broadcast_audio(self, lang: str, audio_bytes: bytes) -> None:
        """
        Send raw PCM bytes to all audio clients in the given room.
        """
        async with self._lock:
            clients = list(self.audio_clients.get(lang, set()))

        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_bytes(audio_bytes)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect_audio(lang, ws)


ws_manager = WSManager()
