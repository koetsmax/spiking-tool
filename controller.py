from tkinter import *
from tkinter import ttk as tk
from sot.Region import Region, core_regions
from threadedsio import ThreadedSocketClient
import traceback
import asyncio


class Client:
    """
    Class to store information about a client
    """

    def __init__(self, name):
        self.name = name
        self.ship_type = "Brigantine"
        self.status = "Unknown"
        self.active = None
        self.active_checkbox = None
        self.name_label = None
        self.ship_listbox = None
        self.status_label = None
        self.port = None


class ClientManager:
    """
    Class to manage all of the clients
    """

    def __init__(self):
        self.clients = {}
        self.biggest_match = None

    def add_client(self, name):
        """
        Add a client to the list of clients
        """
        client = Client(name)
        self.clients[name] = client

    def get_active_clients(self):
        """
        Get a list of all of the active clients (clients with the active checkbox checked)
        """
        return [client for client in self.clients if self.clients[client].active.get()]

    def get_client(self, name):
        """
        Get a client by name
        """
        return self.clients.get(name)

    def set_client_status(self, name, status):
        """
        Set the status of a client
        """
        client = self.get_client(name)
        # if the status is an int, set the last 3 numbers of the port to the status
        if isinstance(status, int):
            status = int(str(status)[2:])
            # if the status is less than 3 characters long. add 0's in front of it until it is 3 characters long
            if len(str(status)) < 3:
                status = "0" * (3 - len(str(status))) + str(status)
            client.port = status
        # check if the status contains "outpost=" and remove it
        if "outpost=" in str(status):
            location = str(status).replace("outpost=", "")
            status = f"{client.port} -- {location}"

        if client:
            client.status = status
            client.status_label.configure(text=status)

    def remove_client(self, name):
        """
        Delete all of the gui elements associated with the client and remove it from the list
        """

        if name in self.clients:
            client = self.get_client(name)
            client.active_checkbox.destroy()
            client.name_label.destroy()
            client.ship_listbox.destroy()
            client.status_label.destroy()
            del self.clients[name]
            print(f"Client {name} removed")

    def update_biggest_match(self, label):
        """
        Update the biggest match label
        """
        # dictionary to count the frequency of each port
        port_counts = {}

        # iterate over all clients and update the port counts
        for client_name, client in self.clients.items():
            if client.port is not None:
                port_counts[client.port] = port_counts.get(client.port, []) + [client_name]

        # find the port with the most matches
        biggest_match = None
        for port, clients in port_counts.items():
            if biggest_match is None or len(clients) > len(port_counts[biggest_match]):
                biggest_match = port

        # format the output string
        if biggest_match:
            matching_clients = ", ".join(port_counts[biggest_match])
            num_matching_clients = len(port_counts[biggest_match])
            label.configure(text=f"Biggest match is {num_matching_clients} with port: {biggest_match} and client(s): {matching_clients}")
            self.biggest_match = num_matching_clients
        else:
            label.configure(text="No matches found")

    def reset_clients(self):
        """
        Reset all of the client ports
        """
        for client_name, client in self.clients.items():
            client.port = None

    def get_biggest_match(self):
        """
        Get the biggest match
        """
        return self.biggest_match


class Controller:
    """
    Class to manage the controller gui
    """

    def __init__(self, root, sio=None):
        self.sio = sio or ThreadedSocketClient(url="http://spiker.famkoets.nl", auth="Controller")
        root.title("Controller script")
        root.option_add("*tearOff", FALSE)
        mainframe = tk.Frame(root, padding="3 3 12 12")
        mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(99, weight=1)
        root.rowconfigure(0, weight=1)
        self.client_manager = ClientManager()
        self.desired_port_mode = False
        self.desired_port = None
        self.auto_spike_mode = False
        self.number_of_ships = None

        self._change_region = StringVar(value="US East - NY/NJ")
        region_combo_box = tk.Combobox(mainframe, textvariable=self._change_region)
        region_combo_box.grid(column=2, row=1, sticky=(W, E))
        regions = list(core_regions.keys())
        print(regions)
        region_combo_box["values"] = regions

        # Bind the ComboboxSelected event to the change_region function
        region_combo_box.bind("<<ComboboxSelected>>", self.change_region)

        self._set_port_spike = BooleanVar(value=False)
        portspike_checkbox = tk.Checkbutton(
            mainframe,
            variable=self._set_port_spike,
            text="Port spike",
            onvalue=1,
            offvalue=0,
            command=self.set_port_spike,
        )
        portspike_checkbox.grid(column=2, row=2, sticky=(W, E))

        self._set_safe_mode = BooleanVar(value=True)
        safe_mode_checkbox = tk.Checkbutton(
            mainframe,
            variable=self._set_safe_mode,
            text="Safe mode",
            onvalue=1,
            offvalue=0,
            command=self.set_safe_mode,
        )
        safe_mode_checkbox.grid(column=2, row=3, sticky=(W, E))

        self._set_desired_port_mode = BooleanVar(value=False)
        desired_port_mode_checkbox = tk.Checkbutton(
            mainframe,
            variable=self._set_desired_port_mode,
            text="Desired port mode",
            onvalue=1,
            offvalue=0,
            command=self.set_desired_port_mode,
        )
        desired_port_mode_checkbox.grid(column=2, row=4, sticky=(W, E))

        self._desired_port = StringVar(value="")
        desired_port_entry = tk.Entry(mainframe, width=7, textvariable=self._desired_port)
        desired_port_entry.grid(column=2, row=5, sticky=(W, E))
        desired_port_entry.bind("<Return>", self.set_desired_port)

        self._set_auto_spike_mode = BooleanVar(value=False)
        auto_spike_mode_checkbox = tk.Checkbutton(
            mainframe,
            variable=self._set_auto_spike_mode,
            text="Auto spike mode",
            onvalue=1,
            offvalue=0,
            command=self.set_auto_spike_mode,
        )
        auto_spike_mode_checkbox.grid(column=2, row=6, sticky=(W, E))

        self._number_of_ships = StringVar(value="")
        number_of_ships = tk.Entry(mainframe, width=7, textvariable=self._number_of_ships)
        number_of_ships.grid(column=2, row=7, sticky=(W, E))
        number_of_ships.bind("<Return>", self.set_number_of_ships)

        # Create a new frame for the list of clients
        self.client_list_frame = tk.Frame(mainframe, padding="5 5 5 5")
        self.client_list_frame.grid(columnspan=4, row=8, sticky=(W, E))
        self.client_list_frame.columnconfigure(0, weight=1)
        self.client_list_frame.columnconfigure(1, weight=1)
        self.client_list_frame.columnconfigure(2, weight=1)
        self.client_list_frame.columnconfigure(3, weight=1)

        tk.Label(self.client_list_frame, text="Active").grid(column=0, row=0, sticky=(E, W))
        tk.Label(self.client_list_frame, text="Instance").grid(column=1, row=0, sticky=(W, E))
        tk.Label(self.client_list_frame, text="Ship type").grid(column=2, row=0, sticky=(W, E))
        tk.Label(self.client_list_frame, text="Status").grid(column=3, row=0, sticky=(W, E))

        self.biggest_match_label = tk.Label(mainframe, text="No matches found")
        self.biggest_match_label.grid(columnspan=4, row=99, sticky=(W, E))

        launch_game_buton = tk.Button(
            mainframe,
            text="launch game",
            command=lambda: self.emit_client_event("launch_game"),
        )
        launch_game_buton.grid(columnspan=4, row=100, sticky=(W, E))

        sail_button = tk.Button(mainframe, text="sail", command=lambda: self.emit_client_event("sail"))
        sail_button.grid(columnspan=4, row=101, sticky=(W, E))

        reset_button = tk.Button(
            mainframe,
            text="reset",
            command=lambda: self.emit_client_event("reset"),
        )
        reset_button.grid(columnspan=4, row=102, sticky=(W, E))

        kill_game_button = tk.Button(
            mainframe,
            text="kill game",
            command=lambda: self.emit_client_event("kill_game"),
        )
        kill_game_button.grid(columnspan=4, row=103, sticky=(W, E))

        stop_functions_button = tk.Button(
            mainframe,
            text="stop running functions",
            command=lambda: self.emit_client_event("stop_functions"),
        )
        stop_functions_button.grid(columnspan=4, row=104, sticky=(W, E))

        for child in mainframe.winfo_children():
            child.grid_configure(padx=5, pady=5)

        root.eval(f"tk::PlaceWindow {root} center")

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
            self.set_safe_mode()
            self.set_desired_port_mode()
            self.set_auto_spike_mode()
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
                        client.ship_type = client.ship_type_var.get()
                        self.sio.emit(
                            "change_ship",
                            data={
                                "client": client.name,
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
            if self.desired_port_mode and not self.desired_port is None:
                client = self.client_manager.get_client(data["client"])
                if isinstance(data["status"], int):
                    status = int(str(data["status"])[2:])
                    # if the status is less than 3 characters long. add 0's in front of it until it is 3 characters long
                    if len(str(status)) < 3:
                        status = "0" * (3 - len(str(status))) + str(status)
                    print(status)
                    if status != self.desired_port.strip():
                        self.emit_client_event("reset", client.name)

                elif data["status"] == "Ready":
                    self.emit_client_event("sail", client.name)
            elif self.auto_spike_mode and not self.number_of_ships is None:
                total_clients = len(self.client_manager.clients)
                print(total_clients)
                # for every client check if the client.port is not None and get the biggest match. check if it is still possible to get the self.number_of_ships using total_clients, biggest_match and the self.number_of_ships
                for client in self.client_manager.clients:
                    if self.client_manager.get_client(client).port is None:
                        print("client.port is None")
                        return
                biggest_match = self.client_manager.get_biggest_match()
                print(total_clients - biggest_match >= self.number_of_ships)
                if biggest_match is None:
                    print("biggest_match is None")
                    return
                if total_clients - biggest_match < self.number_of_ships:
                    print(total_clients - biggest_match < self.number_of_ships)
                    return
                # if it is possible to get the self.number_of_ships using total_clients, reset all the clients

                if total_clients - biggest_match >= self.number_of_ships:
                    self.emit_client_event("reset")

    def change_region(self, *args):
        """
        Change the region of all clients to the region selected in the dropdown menu
        """
        self.sio.emit("region", self._change_region.get())

    def set_port_spike(self):
        """
        Set the portspiking value of all clients to the value selected in the dropdown menu
        """
        self.sio.emit("portspiking", self._set_port_spike.get())

    def set_safe_mode(self):
        """
        Set the safe mode value of all clients to the value selected in the dropdown menu
        """
        self.sio.emit("safe_mode", self._set_safe_mode.get())

    def set_desired_port_mode(self):
        """
        Set the desired port mode of all clients to the value entered in the entry
        """
        self.desired_port_mode = self._set_desired_port_mode.get()
        print(f"Desired port mode set to {self._set_desired_port_mode.get()}")

    def set_desired_port(self, *args):
        """
        Set the desired port of all clients to the value entered in the entry
        """
        self.desired_port = self._desired_port.get()
        print(f"Desired port set to {self.desired_port}")

    def set_auto_spike_mode(self):
        """
        Set the auto spike mode of all clients to the value entered in the entry
        """
        self.auto_spike_mode = self._set_auto_spike_mode.get()
        print(f"Auto spike mode set to {self._set_auto_spike_mode.get()}")

    def set_number_of_ships(self, *args):
        """
        Set the number of ships of all clients to the value entered in the entry
        """
        self.number_of_ships = self._number_of_ships.get()
        print(f"Number of ships set to {self.number_of_ships}")

    def emit_client_event(self, event, *args):
        """
        Emit an event to all clients
        """
        if not args:
            active_clients = self.client_manager.get_active_clients()
        else:
            active_clients = args
        self.sio.emit("client_event", {"event": event, "clients": active_clients})
        if event == "reset":
            self.client_manager.reset_clients()


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
