import sys
import json
import bluetooth
import argparse
import pickle
import signal
import threading
import tkinter as tk
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from skullpkt import Skullpkt
from gui import SkullguiApp
from cmd import CMD


def signal_handler(sig, frame):
    print(' -> Shutting down...')
    sys.exit(0)

class mach:
    def __init__(self, bdaddr: str, gui=False):
        self.bdaddr = bdaddr
        self.sock = None
        self.save_wait = False  # indicate we need to recv from the sock
        self.profiles = None  # saved profiles
        
        if gui:
            self.s = socket(AF_INET, SOCK_STREAM)
            self.s.bind(('', 0))
            self.s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            # SkullguiApp(mach_port=self.s.getsockname()[1])
            gui_thread = threading.Thread(target=SkullguiApp, 
                                          kwargs=dict(mach_port=self.s.getsockname()[1]))
            gui_thread.start()
            
            # wait for connection
            print("waiting...")
            self.s.listen()
            print("accepting...")
            self.conn, addr = self.s.accept()

        self.load()
        # self.connect()
        self.mainloop(gui)

    def mainloop(self, gui):
        print("==========================================================")
        print("Connected. Give a command in the format -> <cmd>::<amount>")
        print("Type ? or help for a list of commands.")
        print("==========================================================")

        while True:
            close = False

            if gui:
                data = input("> ")
            else:
                # get from gui socket!                        
                data = self.conn.listen()
                data = data.decode()
            
            print(data)
            
            profile_name = None
            if not data:
                break

            cmds = data.split(" ")
            pkt = Skullpkt()
            for indiv in cmds:
                if indiv in ['reset', 'close']:
                    # handle without value
                    c = CMD(indiv)
                    pkt.add_cmd(c)
                    if indiv == 'close':
                        close = True

                elif indiv.startswith("save::"):
                    indiv = indiv.split("::")
                    c = CMD(indiv[0])
                    pkt.add_cmd(c)
                    self.save_wait = True
                    profile_name = indiv[1]
                    if indiv[1] in self.profiles.keys():
                        print("=========================")
                        string = input(
                            f'Profile already present with values {self.profiles[indiv[1]]}\nDo you want to overwrite? [Y/n] ')
                        print("=========================")
                        if string == "Y":
                            print("OVERWRITING")
                            self.profiles[indiv[1]] = dict()
                        else:
                            # cancel the save action
                            print("OVERWRITE CANCELLED")
                            self.save_wait = False

                elif indiv == "list":
                    for entry in self.profiles.keys():
                        print(f'{entry} -> {self.profiles[entry]}')
                elif indiv == "?":
                    print("Valid commands...")
                    print(CMD.permitted_cmds())
                else:
                    action = indiv.split("::")
                    # print(action)
                    if action[0] in CMD.permitted_cmds():
                        try:
                            c = CMD(action[0], int(action[1]))
                            pkt.add_cmd(c)
                            # print(pkt.get_pkt_cmds())
                        except ValueError as e:
                            print("\t<" + action[0] + ">" + "BAD COMMAND")
                    else:
                        print("\t<" + action[0] + ">" + "BAD COMMAND")

            if len(pkt.get_pkt_cmds()) != 0:  # only send if there are valid cmds
                data_string = pickle.dumps(pkt)
                self.sock.send(data_string)  # send along the socket to the rpi

            if self.save_wait:
                self.save_wait = False
                data = self.sock.recv(4096)
                data = pickle.loads(data)
                print(data)
                self.profiles[profile_name] = data
                self.save()

            if close:
                self.sock.close()
                sys.exit(0)

    def save(self):
        # dump to disk
        with open('profiles.json', 'w') as fp:
            json.dump(self.profiles, fp)

    def load(self):
        # load from disk
        with open('profiles.json') as fp:
            self.profiles = json.loads(fp.read())

    def connect(self):
        # instantiate and connect to bluetooth socket
        service_matches = bluetooth.find_service(address=self.bdaddr)
        first_match = service_matches[0]
        port = first_match["port"]
        name = first_match["name"]
        host = first_match["host"].decode()

        self.sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.sock.connect((host, port))
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='skullpos client')
    parser.add_argument('bluetooth_addr', type=str)
    parser.add_argument('-gui', action='store_true')
    signal.signal(signal.SIGINT, signal_handler)
    args = parser.parse_args()
    mach(args.bluetooth_addr, args.gui)
