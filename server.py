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

    def _register_handlers(self) -> None:
        @self.sio.event
        async def connect(sid, environ, auth):
            parsed = normalize_auth(auth, sid)
            if parsed["type"] == "controller":
                self.clients[sid] = SpikingServer.Client(
                    sid, parsed["name"], parsed["type"], parsed["name"]
                )
                self.controller = sid
            else:
                existing = self._game_clients()
                display_name = assign_display_name(existing, parsed["name"])
                self.clients[sid] = SpikingServer.Client(
                    sid, parsed["name"], parsed["type"], display_name
                )
                await self.sio.emit(
                    "client_identity",
                    {"display_name": display_name},
                    to=sid,
                )
            await self.sio.enter_room(sid, self.clients[sid].type)
            await self._notify_controller_roster()

        @self.sio.event
        async def disconnect(sid):
            if sid not in self.clients:
                return
            client = self.clients[sid]
            print(f"Client {client.display_name} disconnected")
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
            print(
                f"Join from {self.clients[sid].name if sid in self.clients else sid}: "
                f"game={game} management={management}"
            )
            client = self._display_name_for_sid(sid)
            await self.sio.emit(
                "update_status",
                data={
                    "client": client,
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
                await self.sio.emit(
                    "afk_status",
                    data={"client": client, **data},
                    room=self.controller,
                )
            else:
                await self.sio.emit(
                    "afk_status",
                    data={"client": client, "type": "text", "message": str(data)},
                    room=self.controller,
                )

        @self.sio.event
        async def afk_state(sid, data):
            client = self._display_name_for_sid(sid)
            await self.sio.emit(
                "afk_state",
                data={"client": client, **data},
                room=self.controller,
            )

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
            await self.sio.emit(
                "update_status",
                data={"client": client, "status": data},
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
        async def hold_request_ack(sid, data):
            client = self._display_name_for_sid(sid)
            await self.sio.emit(
                "hold_request_ack",
                data={"client": client, "status": data},
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
