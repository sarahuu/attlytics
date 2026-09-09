import json

from fastapi import WebSocket


class EnrollmentSocketRegistry:
    def __init__(self) -> None:
        self._sockets: dict[str, WebSocket] = {}

    def register(self, installation_id: str, websocket: WebSocket) -> None:
        self._sockets[installation_id] = websocket

    def unregister(self, installation_id: str, websocket: WebSocket) -> None:
        if self._sockets.get(installation_id) is websocket:
            self._sockets.pop(installation_id, None)

    def is_connected(self, installation_id: str) -> bool:
        return installation_id in self._sockets

    async def send_json(self, installation_id: str, message: dict) -> bool:
        websocket = self._sockets.get(installation_id)
        if websocket is None:
            return False
        try:
            await websocket.send_text(json.dumps(message))
            return True
        except Exception:  # noqa: BLE001 - socket went away
            self.unregister(installation_id, websocket)
            return False


enrollment_sockets = EnrollmentSocketRegistry()
