import logging

import socketio
import uvicorn

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
        def __init__(self, sid, name="", client_type="client"):
            self.sio = sid
            self.name = name
            self.type = client_type

    def __init__(self):
        self.sio = socketio.AsyncServer(async_mode="asgi")
        self.app = socketio.ASGIApp(self.sio)
        self.clients = {}
        self.controller = None
        self.region = None

        @self.sio.event
        async def connect(sid, environ, auth):
            parsed = normalize_auth(auth, sid)
            self.clients[sid] = SpikingServer.Client(sid, parsed["name"], parsed["type"])
            if parsed["type"] == "controller":
                self.controller = sid
            await self.sio.enter_room(sid, self.clients[sid].type)
            client_names = [self.clients[client].name for client in self.clients]
            if self.controller:
                await self.sio.emit("client_connect", data=client_names, room=self.controller)

        @self.sio.event
        async def disconnect(sid):
            if sid in self.clients:
                print(f"Client {self.clients[sid].name} disconnected")
                del self.clients[sid]
                client_names = [self.clients[client].name for client in self.clients]
                if self.controller:
                    await self.sio.emit("client_disconnect", data=client_names, room=self.controller)

        @self.sio.event
        async def join(sid, data):
            game = f"{data['game_ip']}:{data['game_port']}"
            management = f"{data['management_ip']}:{data['management_port']}"
            print(
                f"Join from {self.clients[sid].name if sid in self.clients else sid}: "
                f"game={game} management={management}"
            )
            client = self.clients[sid].name if sid in self.clients else sid
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
            await self.sio.emit(data["event"], data=data["clients"])

        @self.sio.event
        async def update_status(sid, data):
            client = self.clients[sid].name if sid in self.clients else sid
            await self.sio.emit(
                "update_status",
                data={"client": client, "status": data},
                room=self.controller,
            )

        @self.sio.event
        async def client_metric(sid, data):
            client = self.clients[sid].name if sid in self.clients else sid
            await self.sio.emit(
                "client_metric",
                data={"client": client, **data},
                room=self.controller,
            )

        @self.sio.event
        async def hold_request_ack(sid, data):
            client = self.clients[sid].name if sid in self.clients else sid
            await self.sio.emit(
                "hold_request_ack",
                data={"client": client, "status": data},
                room=self.controller,
            )

        @self.sio.event
        async def invite_request(sid, data):
            await self.sio.emit("invite_request", data=data)

    def run(self):
        uvicorn.run(self.app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    setup_logging()
    server = SpikingServer()
    logger.info("Starting spiking server")
    server.run()
