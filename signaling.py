"""Thin client for the public PeerJS signaling server.

We do NOT use the PeerJS client library. We only borrow its free, public
WebSocket relay to swap a single WebRTC offer/answer between two peers. Once
that handshake is done the two machines talk to each other directly over
WebRTC and this connection just idles with heartbeats.

Message envelope used by the server:
    {"type": "OFFER"|"ANSWER"|..., "dst": <peer id>, "payload": {...}}
The server fills in "src" when it relays a message to the destination peer.
"""
import asyncio
import json
import logging
import secrets

import websockets

log = logging.getLogger("anyhelp.signaling")

_HOST = "0.peerjs.com"
_PORT = 443
_KEY = "peerjs"
_HEARTBEAT_SECONDS = 5


class IDTaken(Exception):
    """The chosen peer id is already registered on the server."""


class SignalingError(Exception):
    pass


def _ws_url(peer_id: str, token: str) -> str:
    return (
        f"wss://{_HOST}:{_PORT}/peerjs?key={_KEY}"
        f"&id={peer_id}&token={token}&version=1.5.4"
    )


class Signaling:
    """Register a peer id and exchange relayed messages with other peers."""

    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        self._token = secrets.token_hex(10)
        self._ws = None
        self._inbox: asyncio.Queue = asyncio.Queue()
        self._reader_task = None
        self._heartbeat_task = None

    async def connect(self) -> None:
        url = _ws_url(self.peer_id, self._token)
        self._ws = await websockets.connect(url, max_size=None, open_timeout=20)
        first = json.loads(await self._ws.recv())
        kind = first.get("type")
        if kind == "ID-TAKEN":
            await self._ws.close()
            raise IDTaken()
        if kind != "OPEN":
            await self._ws.close()
            raise SignalingError(f"unexpected first message: {first}")
        self._reader_task = asyncio.create_task(self._reader())
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        log.info("registered as %s", self.peer_id)

    async def _reader(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                await self._inbox.put(msg)
        except Exception as exc:  # connection dropped
            await self._inbox.put({"type": "_CLOSED", "error": str(exc)})
        else:
            await self._inbox.put({"type": "_CLOSED", "error": "closed"})

    async def _heartbeat(self) -> None:
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_SECONDS)
                await self._ws.send(json.dumps({"type": "HEARTBEAT"}))
        except Exception:
            pass

    async def recv(self) -> dict:
        """Return the next message from the server (blocks)."""
        return await self._inbox.get()

    async def send(self, type_: str, dst: str, payload: dict) -> None:
        await self._ws.send(json.dumps({"type": type_, "dst": dst, "payload": payload}))

    async def close(self) -> None:
        for task in (self._heartbeat_task, self._reader_task):
            if task is not None:
                task.cancel()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
