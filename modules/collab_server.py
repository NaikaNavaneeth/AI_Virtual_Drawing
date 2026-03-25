"""
modules/collab_server.py  —  WebSocket-based collaborative drawing server.

Start the server:
    python -m modules.collab_server

Or from within the drawing app (if COLLAB_ENABLED=True):
    from modules.collab_server import CollabServer
    srv = CollabServer(); srv.start()

Protocol (JSON messages):
    Client → Server: {"type": "draw",  "x": int, "y": int, "px": int, "py": int,
                       "color": [B,G,R], "thickness": int, "user_id": str}
    Client → Server: {"type": "erase", "x": int, "y": int, "radius": int}
    Client → Server: {"type": "clear"}
    Client → Server: {"type": "shape", "shape": str, "points": [[x,y]...]}
    Server → All:    same message, broadcast verbatim + "user_id" field added
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from typing import Optional, Set

_WS_OK = False
try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    _WS_OK = True
except ImportError:
    pass

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import COLLAB_HOST, COLLAB_PORT


class CollabServer:
    """
    Lightweight broadcast WebSocket server for collaborative drawing.
    Runs in a background thread so it doesn't block the main CV loop.
    """

    def __init__(self, host: str = COLLAB_HOST, port: int = COLLAB_PORT):
        if not _WS_OK:
            raise ImportError(
                "websockets package not found.\n"
                "Install it: pip install websockets"
            )
        self.host  = host
        self.port  = port
        self._clients: Set[WebSocketServerProtocol] = set()
        self._thread: Optional[threading.Thread]    = None
        self._loop:   Optional[asyncio.AbstractEventLoop] = None

    def start(self):
        """Start the server in a daemon thread."""
        self._thread = threading.Thread(
            target=self._run_forever, daemon=True, name="CollabServer"
        )
        self._thread.start()
        print(f"[CollabServer] Started at ws://{self.host}:{self.port}")

    def stop(self):
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # ── Internal ──────────────────────────────────────────────────────────
    def _run_forever(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        async with websockets.serve(self._handler, self.host, self.port):
            await asyncio.Future()   # run forever

    async def _handler(self, ws: WebSocketServerProtocol, path: str = "/"):
        self._clients.add(ws)
        user_id = str(uuid.uuid4())[:8]
        print(f"[CollabServer] Client connected: {user_id}  total={len(self._clients)}")
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    msg["user_id"] = user_id
                    await self._broadcast(json.dumps(msg), sender=ws)
                except json.JSONDecodeError:
                    pass
        finally:
            self._clients.discard(ws)
            print(f"[CollabServer] Client left: {user_id}  total={len(self._clients)}")

    async def _broadcast(self, message: str, sender=None):
        targets = self._clients - ({sender} if sender else set())
        if targets:
            await asyncio.gather(*[c.send(message) for c in targets],
                                  return_exceptions=True)


# ═══════════════════════════════════════════════════════════════════════
#  CollabClient  —  used by the drawing module to connect to a server
# ═══════════════════════════════════════════════════════════════════════

class CollabClient:
    """
    Async WebSocket client.  Sends drawing events and receives updates from peers.
    """

    def __init__(self, uri: str = None):
        if not _WS_OK:
            raise ImportError("websockets package not found.")
        self.uri  = uri or f"ws://{COLLAB_HOST}:{COLLAB_PORT}"
        self._ws  = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._recv_queue: asyncio.Queue = None
        self.connected = False

    def connect(self, on_message=None):
        """Connect in a background thread. on_message(dict) called for each peer event."""
        self._on_message = on_message
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="CollabClient"
        )
        self._thread.start()

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self):
        self._recv_queue = asyncio.Queue()
        try:
            async with websockets.connect(self.uri) as ws:
                self._ws = ws
                self.connected = True
                print(f"[CollabClient] Connected to {self.uri}")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        if self._on_message:
                            self._on_message(msg)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[CollabClient] Connection error: {e}")
        finally:
            self.connected = False

    def send(self, msg: dict):
        """Send a drawing event (fire-and-forget)."""
        if not self.connected or not self._ws or not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self._ws.send(json.dumps(msg)), self._loop)

    def send_stroke(self, x: int, y: int, px: int, py: int,
                    color: tuple, thickness: int):
        self.send({
            "type": "draw",
            "x": x, "y": y, "px": px, "py": py,
            "color": list(color), "thickness": thickness,
        })

    def send_erase(self, x: int, y: int, radius: int):
        self.send({"type": "erase", "x": x, "y": y, "radius": radius})

    def send_clear(self):
        self.send({"type": "clear"})

    def send_shape(self, shape: str, points: list):
        self.send({"type": "shape", "shape": shape, "points": points})


# ── CLI: run server standalone ───────────────────────────────────────────────
if __name__ == "__main__":
    import time
    srv = CollabServer()
    srv.start()
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.stop()
        print("Server stopped.")
