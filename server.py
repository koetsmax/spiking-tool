from __future__ import annotations

import logging

import socketio
import uvicorn

from spiking_tool.client_identity import assign_display_name
from spiking_tool.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def normalize_auth(auth: str | dict | None, sid: str) -> dict[str, str]:
    if auth is None:
        return {"name": sid, "type": "client"}
    if isinstance(auth, str):
        if auth == "Controller":
            return {"name": "Controller", "type": "controller"}
        return {"name": auth, "type": "client"}
    if isinstance(auth, dict):
        return {
            "name": auth.get("name", sid),
            "type": auth.get("type", "client"),
        }
    return {"name": sid, "type": "client"}


class SpikingServer:
    class Client:
        def __init__(self, sid, name="", client_type="client", display_name=""):
            self.sio = sid
            self.name = name
            self.type = client_type
            self.display_name = display_name or name

    def __init__(self):
        self.sio = socketio.AsyncServer(async_mode="asgi")
        self.app = socketio.ASGIApp(self.sio)
        self.clients = {}
        self.controller = None
        self.region = None
        # Last AFK payloads per client — replayed when the controller (re)connects.
        self._afk_state_cache: dict[str, dict] = {}
        self._afk_status_cache: dict[str, dict] = {}
        self._register_handlers()

    def _game_clients(self) -> list["SpikingServer.Client"]:
        return [client for client in self.clients.values() if client.type == "client"]

    def _game_client_roster(self) -> list[str]:
        return [client.display_name for client in self._game_clients()]

    def _client_for_sid(self, sid: str) -> SpikingServer.Client | None:
        return self.clients.get(sid)

    def _display_name_for_sid(self, sid: str) -> str:
        client = self._client_for_sid(sid)
        return client.display_name if client else sid

    async def _notify_controller_roster(self) -> None:
        if self.controller:
            await self.sio.emit(
                "client_connect",
                data=self._game_client_roster(),
                room=self.controller,
            )

    async def _replay_afk_to_controller(self) -> None:
        if not self.controller:
            return
        connected = set(self._game_client_roster())
        for display_name, state in self._afk_state_cache.items():
            if display_name not in connected:
                continue
            await self.sio.emit(
                "afk_state",
                data={"client": display_name, **state},
                room=self.controller,
            )
        for display_name, status in self._afk_status_cache.items():
            if display_name not in connected:
                continue
            await self.sio.emit(
                "afk_status",
                data={"client": display_name, **status},
                room=self.controller,
            )

    async def _request_clients_session_sync(self) -> None:
        for client in self._game_clients():
            await self.sio.emit("request_session_sync", to=client.sio)

    async def _on_controller_ready(self) -> None:
        await self._notify_controller_roster()
        await self._replay_afk_to_controller()
        await self._request_clients_session_sync()

    def _cache_afk_state(self, display_name: str, data: dict) -> None:
        self._afk_state_cache[display_name] = {
            "enabled": bool(data.get("enabled")),
            "preserve_status": bool(data.get("preserve_status")),
        }

    def _cache_afk_status(self, display_name: str, data: dict) -> None:
        if data.get("type") == "clear":
            self._afk_status_cache.pop(display_name, None)
            return
        self._afk_status_cache[display_name] = dict(data)

    async def _forward_afk_state(self, display_name: str, data: dict) -> None:
        self._cache_afk_state(display_name, data)
        if not self.controller:
            return
        await self.sio.emit(
            "afk_state",
            data={"client": display_name, **data},
            room=self.controller,
        )

    async def _forward_afk_status(self, display_name: str, data: dict) -> None:
        self._cache_afk_status(display_name, data)
        if not self.controller:
            return
        await self.sio.emit(
            "afk_status",
            data={"client": display_name, **data},
            room=self.controller,
        )

    def _register_handlers(self) -> None:
        @self.sio.event
        async def connect(sid, environ, auth):
            parsed = normalize_auth(auth, sid)
            if parsed["type"] == "controller":
                self.clients[sid] = SpikingServer.Client(sid, parsed["name"], parsed["type"], parsed["name"])
                self.controller = sid
            else:
                existing = self._game_clients()
                display_name = assign_display_name(existing, parsed["name"])
                self.clients[sid] = SpikingServer.Client(sid, parsed["name"], parsed["type"], display_name)
                await self.sio.emit(
                    "client_identity",
                    {"display_name": display_name},
                    to=sid,
                )
            await self.sio.enter_room(sid, self.clients[sid].type)
            if parsed["type"] == "client":
                logger.info("Client connected: %s (auth name=%s)", display_name, parsed["name"])
            elif parsed["type"] == "controller":
                logger.info("Controller connected")
            if parsed["type"] == "controller":
                await self._on_controller_ready()
            else:
                await self._notify_controller_roster()

        @self.sio.event
        async def disconnect(sid):
            if sid not in self.clients:
                return
            client = self.clients[sid]
            if client.type == "client":
                logger.info("Client disconnected: %s", client.display_name)
                self._afk_state_cache.pop(client.display_name, None)
                self._afk_status_cache.pop(client.display_name, None)
            elif client.type == "controller":
                logger.info("Controller disconnected")
            if sid == self.controller:
                self.controller = None
            del self.clients[sid]
            if self.controller:
                await self.sio.emit(
                    "client_disconnect",
                    data=self._game_client_roster(),
                    room=self.controller,
                )

        @self.sio.event
        async def join(sid, data):
            game = f"{data['game_ip']}:{data['game_port']}"
            management = f"{data['management_ip']}:{data['management_port']}"
            client_name = self._display_name_for_sid(sid)
            logger.info(
                "Join from %s: game=%s management=%s",
                client_name,
                game,
                management,
            )
            await self.sio.emit(
                "update_status",
                data={
                    "client": client_name,
                    "status": data["management_port"],
                    "match": data,
                },
                room=self.controller,
            )

        @self.sio.event
        async def name(sid, data):
            self.clients[sid] = data["name"]

        @self.sio.event
        async def region(sid, data):
            await self.sio.emit("region", data)

        @self.sio.event
        async def portspiking(sid, data):
            await self.sio.emit("portspiking", data)

        @self.sio.event
        async def change_ship(sid, data):
            await self.sio.emit("client_ship", data=data)

        @self.sio.event
        async def ship_state(sid, data):
            if not self.controller:
                return
            if not isinstance(data, dict):
                return
            client = self._display_name_for_sid(sid)
            await self.sio.emit(
                "client_ship_state",
                data={"client": client, "ship_type": data.get("ship_type", "Brigantine")},
                room=self.controller,
            )

        @self.sio.event
        async def client_event(sid, data):
            event = data["event"]
            targets = data.get("clients", [])
            for client_sid, client in list(self.clients.items()):
                if client.type != "client" or client.display_name not in targets:
                    continue
                if event == "sail" and isinstance(data, dict):
                    await self.sio.emit(
                        "sail",
                        data={
                            "clients": [client.display_name],
                            "sail_delay_seconds": data.get("sail_delay_seconds", 0),
                        },
                        to=client_sid,
                    )
                else:
                    await self.sio.emit(event, data=[client.display_name], to=client_sid)

        @self.sio.event
        async def request_roster(sid, data=None):
            del data
            if sid != self.controller:
                return
            await self._notify_controller_roster()
            await self._replay_afk_to_controller()

        @self.sio.event
        async def kill_client(sid, data):
            if sid != self.controller:
                logger.warning("kill_client ignored: sender %s is not the controller", sid)
                return
            if not isinstance(data, dict):
                logger.warning("kill_client ignored: invalid payload %r", data)
                return
            targets = set(data.get("clients", []))
            if not targets:
                logger.warning("kill_client ignored: no targets in %r", data)
                return
            for client_sid, client in list(self.clients.items()):
                if client.type == "client" and client.display_name in targets:
                    logger.info("Sending shutdown_client to %s", client.display_name)
                    await self.sio.emit("shutdown_client", to=client_sid)

        @self.sio.event
        async def afk_status(sid, data):
            client = self._display_name_for_sid(sid)
            if isinstance(data, dict):
                await self._forward_afk_status(client, data)
            else:
                await self._forward_afk_status(
                    client,
                    {"type": "text", "message": str(data)},
                )

        @self.sio.event
        async def afk_state(sid, data):
            if not isinstance(data, dict):
                return
            client = self._display_name_for_sid(sid)
            await self._forward_afk_state(client, data)

        @self.sio.event
        async def set_anti_afk(sid, data):
            if sid != self.controller:
                return
            if not isinstance(data, dict):
                return
            target = data.get("client")
            for client_sid, client in list(self.clients.items()):
                if client.type == "client" and client.display_name == target:
                    await self.sio.emit(
                        "anti_afk",
                        {"enabled": bool(data.get("enabled"))},
                        to=client_sid,
                    )
                    return

        @self.sio.event
        async def update_status(sid, data):
            client = self._display_name_for_sid(sid)
            if isinstance(data, dict) and "status" in data:
                payload = {"client": client, "status": data["status"]}
                if data.get("match") is not None:
                    payload["match"] = data["match"]
            else:
                payload = {"client": client, "status": data}
            await self.sio.emit(
                "update_status",
                data=payload,
                room=self.controller,
            )

        @self.sio.event
        async def client_metric(sid, data):
            client = self._display_name_for_sid(sid)
            await self.sio.emit(
                "client_metric",
                data={"client": client, **data},
                room=self.controller,
            )

        @self.sio.event
        async def invite_request(sid, data):
            await self.sio.emit("invite_request", data=data)

        @self.sio.event
        async def client_log(sid, data):
            if not self.controller:
                return
            client = self._display_name_for_sid(sid)
            await self.sio.emit(
                "client_log",
                data={
                    "client": client,
                    "message": data.get("message", ""),
                    "level": data.get("level", "INFO"),
                },
                room=self.controller,
            )

    def run(self):
        uvicorn.run(self.app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    setup_logging()
    server = SpikingServer()
    logger.info("Starting spiking server")
    server.run()
