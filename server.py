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

        @self.sio.event
        async def connect(sid, environ, auth):
            try:
                self.clients[sid] = SpikingServer.Client(sid, auth["name"], auth["type"])
            except TypeError:
                self.clients[sid] = SpikingServer.Client(sid, auth)

            if auth == "Controller":
                self.controller = sid
            self.sio.enter_room(sid, self.clients[sid].type)
            client_names = [self.clients[client].name for client in self.clients]
            if self.controller:
                await self.sio.emit("client_connect", data=client_names, room=self.controller)

        @self.sio.event()
        async def disconnect(sid):
            if sid in self.clients:
                print(f"Client {self.clients[sid].name} disconnected")
                del self.clients[sid]
                client_names = [self.clients[client].name for client in self.clients]
                if self.controller:
                    await self.sio.emit("client_disconnect", data=client_names, room=self.controller)

        @self.sio.event
        async def join(sid, data):
            print(f"Join from {self.clients[sid].name if sid in self.clients else sid}: {data['ip']}:{data['port']}")
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
            await self.sio.emit("region", data)

        @self.sio.event
        async def portspiking(sid, data):
            await self.sio.emit("portspiking", data)

        @self.sio.event
        async def safe_mode(sid, data):
            await self.sio.emit("safe_mode", data)

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

    def run(self):
        uvicorn.run(self.app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    server = SpikingServer()
    server.run()
