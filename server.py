import time

import socketio
import uvicorn

from sot.Region import Region


class SpikingServer:
    class Client:
        def __init__(self, sio, name="", type="client"):
            self.sio = sio
            self.name = name
            self.type = type

    def __init__(self):
        self.sio = socketio.AsyncServer(async_mode="asgi")
        self.app = socketio.ASGIApp(self.sio)
        self.clients = {}
        self.controller = False
        self.region = None
        self.portspiking = None

        @self.sio.event
        async def connect(sid, environ, auth):
            try:
                self.clients[sid] = SpikingServer.Client(
                    sid, auth["name"], auth["type"]
                )
            except TypeError:
                self.clients[sid] = SpikingServer.Client(sid, auth)

            if auth == "Controller":
                self.controller = sid
            self.sio.enter_room(sid, self.clients[sid].type)
            client_names = [self.clients[client].name for client in self.clients]
            if self.controller:
                await self.sio.emit(
                    "client_connect", data=client_names, room=self.controller
                )

        @self.sio.event()
        async def disconnect(sid):
            if sid in self.clients:
                print(f"Client {self.clients[sid].name} disconnected")
                del self.clients[sid]
                client_names = [self.clients[client].name for client in self.clients]
                if self.controller:
                    await self.sio.emit(
                        "client_disconnect", data=client_names, room=self.controller
                    )

        @self.sio.event
        async def join(sid, data):
            # current time as 13:37 (24h)
            jtime = time.strftime("%H:%M", time.localtime())
            print(
                f"[{jtime}] Join from {self.clients[sid].name if sid in self.clients else sid}: {data['ip']}:{data['port']}"
            )
            client = self.clients[sid].name if sid in self.clients else sid
            await self.sio.emit(
                "update_status",
                data={"client": client, "status": data["port"]},
                room=self.controller,
            )

        @self.sio.event
        async def name(sid, data):
            self.clients[sid] = data["name"]

        @self.sio.event
        async def region(sid, data):
            print(f"region change: {data}")
            self.region = Region.fromName(data)
            await self.sio.emit("region", self.region.name)

        @self.sio.event
        async def portspiking(sid, data):
            print(f"Portspike set to {data}")
            self.portspiking = data
            await self.sio.emit("portspiking", data)

        @self.sio.event
        async def change_ship(sid, data):
            print(f"{data['name']} changed to {data['ship_type']}")

            client_names = [self.clients[client].name for client in self.clients]
            client_sids = [client for client in self.clients]

            # match the client names to the client sids like "name": "main2", "sid": "123456789"
            client_data = [
                {"name": name, "sid": sid}
                for name, sid in zip(client_names, client_sids)
            ]

            for client in client_data:
                if client["name"] == data["name"]:
                    data["sid"] = client["sid"]

            # send the change to the client specified in data
            await self.sio.emit("client_ship", data=data["ship_type"], room=data["sid"])

        @self.sio.event
        async def launch_game(sid, data):
            await self.sio.emit("launch_game", data=data)

        @self.sio.event
        async def sail(sid, data):
            await self.sio.emit("sail", data=data)

        @self.sio.event
        async def reset(sid, data):
            await self.sio.emit("reset", data=data)

        @self.sio.event
        async def kill_game(sid, data):
            await self.sio.emit("kill_game", data=data)

        @self.sio.event
        async def stop_everything(sid, data):
            await self.sio.emit("stop_everything", data=data)

        @self.sio.event
        async def update_status(sid, data):
            client = self.clients[sid].name if sid in self.clients else sid
            await self.sio.emit(
                "update_status",
                data={"client": client, "status": data},
                room=self.controller,
            )

    def run(self):
        uvicorn.run(self.app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    print(time.strftime("%H:%M", time.localtime()))
    server = SpikingServer()
    server.run()
