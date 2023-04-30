from tkinter import *
from tkinter import ttk as tk
from sot import Region
from threadedsio import ThreadedSocketClient
import traceback


# pylint: disable=all
class Client:
    def __init__(self, name):
        self.name = name
        self.ship_type = "Brigantine"
        self.status = "Offline"
        self.active = None
        self.active_checkbox = None
        self.name_label = None
        self.ship_listbox = None
        self.status_label = None


class ClientManager:
    def __init__(self):
        self.clients = {}

    def add_client(self, name):
        client = Client(name)
        self.clients[name] = client

    def get_active_clients(self):
        return [client for client in self.clients if self.clients[client].active.get()]

    def get_client(self, name):
        return self.clients.get(name)

    def set_client_status(self, name, status):
        if isinstance(status, int):
            status = int(str(status)[2:])
            # if the status is less than 3 characters long. add 0's in front of it untiul it is 3 characters long
            if len(str(status)) < 3:
                status = "0" * (3 - len(str(status))) + str(status)

        client = self.get_client(name)
        if client:
            client.status = status
            print(f"Client {name} status set to {status}")
            client.status_label.configure(text=status)

    def remove_client(self, name):
        # delete all of the gui elements associated with the client and remove it from the list
        print(f"Removing client {name}")
        if name in self.clients:
            client = self.get_client(name)
            client.active_checkbox.destroy()
            client.name_label.destroy()
            client.ship_listbox.destroy()
            client.status_label.destroy()
            del self.clients[name]
            print(f"Client {name} removed")

    def update_biggest_match(self, label):
        # dictionary to count the frequency of each status
        status_counts = {}

        # iterate over all clients and update the status counts
        for client_name, client in self.clients.items():
            # check if the length is 3 characters long
            if len(str(client.status)) == 3:
                status_counts[client.status] = status_counts.get(client.status, []) + [
                    client_name
                ]

        # find the status with the most matches
        biggest_match = None
        for status, clients in status_counts.items():
            if biggest_match is None or len(clients) > len(
                status_counts[biggest_match]
            ):
                biggest_match = status

        # format the output string
        if biggest_match:
            matching_clients = ", ".join(status_counts[biggest_match])
            num_matching_clients = len(status_counts[biggest_match])
            label.configure(
                text=f"Biggest match is {num_matching_clients} with port: {biggest_match} and client(s): {matching_clients}"
            )
        else:
            label.configure(text="No matching status found")


class Controller:
    def __init__(self, root, sio=None):
        self.root = root
        self.sio = sio or ThreadedSocketClient(
            url="http://spiker.famkoets.nl", auth="Controller"
        )
        self.root.title("Controller script")
        self.root.option_add("*tearOff", FALSE)
        self.mainframe = tk.Frame(self.root, padding="3 3 12 12")
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=1)
        self.root.columnconfigure(3, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.client_manager = ClientManager()

        self._change_region = StringVar(value="US East (NY/NJ)")
        self.region_combo_box = tk.Combobox(
            self.mainframe, textvariable=self._change_region
        )
        self.region_combo_box.grid(column=2, row=1, sticky=(W, E))
        self.region_combo_box["values"] = Region.getRegions()

        # Bind the ComboboxSelected event to the change_region function
        self.region_combo_box.bind("<<ComboboxSelected>>", self.change_region)

        self._set_port_spike = BooleanVar(value=False)
        self.portspike_checkbox = tk.Checkbutton(
            self.mainframe,
            variable=self._set_port_spike,
            text="Port spike",
            onvalue=1,
            offvalue=0,
            command=self.set_port_spike,
        )
        self.portspike_checkbox.grid(column=2, row=2, sticky=(W, E))

        # Create a new frcame for the list of clients
        self.client_list_frame = tk.Frame(self.mainframe, padding="5 5 5 5")
        self.client_list_frame.grid(columnspan=4, row=6, sticky=(W, E))
        self.client_list_frame.columnconfigure(0, weight=1)
        self.client_list_frame.columnconfigure(1, weight=1)
        self.client_list_frame.columnconfigure(2, weight=1)
        self.client_list_frame.columnconfigure(3, weight=1)

        tk.Label(self.client_list_frame, text="Active").grid(
            column=0, row=0, sticky=(E, W)
        )
        tk.Label(self.client_list_frame, text="Instance").grid(
            column=1, row=0, sticky=(W, E)
        )
        tk.Label(self.client_list_frame, text="Ship type").grid(
            column=2, row=0, sticky=(W, E)
        )
        tk.Label(self.client_list_frame, text="Status").grid(
            column=3, row=0, sticky=(W, E)
        )

        self.biggest_match_label = tk.Label(self.mainframe, text="Biggest match: N/A")
        self.biggest_match_label.grid(columnspan=4, row=99, sticky=(W, E))

        self.launch_game_buton = tk.Button(
            self.mainframe, text="launch game", command=self.launch_game
        )
        self.launch_game_buton.grid(columnspan=4, row=100, sticky=(W, E))

        self.sail_button = tk.Button(self.mainframe, text="sail", command=self.sail)
        self.sail_button.grid(columnspan=4, row=101, sticky=(W, E))

        self.reset_button = tk.Button(self.mainframe, text="reset", command=self.reset)
        self.reset_button.grid(columnspan=4, row=102, sticky=(W, E))

        self.kill_game_button = tk.Button(
            self.mainframe, text="kill game", command=self.kill_game
        )
        self.kill_game_button.grid(columnspan=4, row=103, sticky=(W, E))

        for child in self.mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.root.eval(f"tk::PlaceWindow {root} center")

        @self.sio.event()
        def region(data):
            self._change_region.set(data)

        @self.sio.event()
        def portspiking(data):
            self._set_port_spike.set(data)

        @self.sio.event()
        def client_connect(data):
            self.change_region()
            self.set_port_spike()
            for client in data:
                if client != "Controller" and client not in self.client_manager.clients:
                    self.client_manager.add_client(client)

            # Create labels and listboxes for each client
            ship_type_vars = {}  # store StringVar objects in a dictionary
            for i, client_name in enumerate(self.client_manager.clients):
                client = self.client_manager.get_client(client_name)

                # execute the following code if the client is not already in the list
                if client.name_label is None:
                    print(f"Adding {client.name} to the GUI")

                    # create checkbox
                    client.active = BooleanVar(value=True)
                    active_checkbox = tk.Checkbutton(
                        self.client_list_frame,
                        variable=client.active,
                        onvalue=1,
                        offvalue=0,
                    )
                    active_checkbox.grid(column=0, row=i + 1, sticky=(W, E))

                    client.active_checkbox = active_checkbox

                    # Create client name label
                    name_label = tk.Label(self.client_list_frame, text=client.name)
                    name_label.grid(column=1, row=i + 1, sticky=(W, E))

                    client.name_label = name_label

                    # Create client ship listbox
                    ship_type_var = StringVar(value=client.ship_type)
                    ship_listbox = tk.Combobox(
                        self.client_list_frame,
                        height=1,
                        width=15,
                        textvariable=ship_type_var,
                    )
                    ship_listbox.grid(column=2, row=i + 1, sticky=(W, E))
                    ship_listbox["values"] = [
                        "Sloop",
                        "Brigantine",
                        "Galleon",
                        "Captaincy",
                    ]

                    client.ship_type_var = ship_type_var
                    client.ship_listbox = ship_listbox

                    # Set up a callback to update the client's ship type when the user changes the ship_listbox
                    def ship_type_changed(event, client=client):
                        print(
                            f"Changing ship type to {client.ship_type_var.get()} for {client.name}"
                        )
                        client.ship_type = client.ship_type_var.get()
                        self.sio.emit(
                            "change_ship",
                            data={
                                "name": client.name,
                                "ship_type": client.ship_type_var.get(),
                            },
                        )

                    ship_listbox.bind("<<ComboboxSelected>>", ship_type_changed)

                    # Save a reference to the StringVar in the dictionary
                    ship_type_vars[client_name] = ship_type_var

                    # Create client status label
                    status_label = tk.Label(self.client_list_frame, text=client.status)
                    status_label.grid(column=3, row=i + 1, sticky=(W, E))

                    client.status_label = status_label

                    for child in self.client_list_frame.winfo_children():
                        child.grid_configure(padx=10, pady=5)

        @self.sio.event()
        def client_disconnect(data):
            # remove the clients that are not in data
            for client in self.client_manager.clients.copy().items():
                if client[0] not in data:
                    self.client_manager.remove_client(client[0])

        @self.sio.event()
        def update_status(data):
            self.client_manager.set_client_status(data["client"], data["status"])
            self.client_manager.update_biggest_match(self.biggest_match_label)

    def change_region(self, *args):
        self.sio.emit("region", self._change_region.get())

    def set_port_spike(self):
        if "selected" in self.portspike_checkbox.state():
            self.sio.emit("portspiking", True)
        else:
            self.sio.emit("portspiking", False)

    def launch_game(self):
        # Get the list of clients that have the client.active_checkbox checked
        active_clients = self.client_manager.get_active_clients()
        self.sio.emit("launch_game", data=active_clients)

    def sail(self):
        active_clients = self.client_manager.get_active_clients()
        self.sio.emit("sail", data=active_clients)

    def reset(self):
        active_clients = self.client_manager.get_active_clients()
        self.sio.emit("reset", data=active_clients)

    def kill_game(self):
        active_clients = self.client_manager.get_active_clients()
        self.sio.emit("kill_game", data=active_clients)


# Start the SocketIO client
if __name__ == "__main__":
    try:
        root = Tk()
        controller = Controller(root)

        def events():
            controller.sio.events.processEvents()
            root.after(50, events)

        events()
        root.mainloop()
    except:
        traceback.print_exc()
