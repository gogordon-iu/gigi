import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER
from scriptAssets import get_scripts
import socket, psutil
from microphone import set_speaker_volume
import os
import subprocess
# -*- coding: utf-8 -*-

# initialize Character
# Ask what to do
# [run script]
# Which script
# [from a known list]
# ask for confirmation
# [yes -> run, no -> fo to "which script"]


list_of_scripts = get_scripts()
print("List of scripts:")
print(list_of_scripts)

script_options = json.dumps(list(list_of_scripts.keys()) + ["[unk]"])

class WakeUp(ScriptGraph) : 
    def __init__(self):
        super().__init__()

        self.data["ip"] = None
        self.data["wifi network"] = None
        self.data["wifi password"] = None

    def init_graph(self):
        # Add text chunk
        #DEBUG
        self.graph.add_node("start", type=["speak", "move"], 
                            text="It's me again, Gigi.",
                            motors="wave_hello")
       
        self.graph.add_node("wakeup_01", type="speak",
                            text="What do you want to do?")
        self.graph.add_edge("start", 
                            "wakeup_01", 
                            label="start speak")

        self.graph.add_node("wakeup_02", type="hear", 
                            words='["run script", "bye", "show wifi", "connect"]')
        self.graph.add_edge("wakeup_01", 
                            "wakeup_02", 
                            label="ask what to do")
        
        # show IP---
        self.graph.add_node("wakeup_05", type="get_ip")
        self.graph.add_edge("wakeup_02", 
                            "wakeup_05", 
                            label="show wifi")
        
        self.graph.add_node("wakeup_06", type=["show", "pause"],
                            pause={"after": 5.0},
                            caption="Can't find my IP address.")
        self.graph.add_edge("wakeup_05", 
                            "wakeup_06", 
                            label="show wifi")
        self.graph.add_edge("wakeup_06", 
                            "wakeup_01", 
                            label="back to ask")

        # connect to wifi---
        self.graph.add_node("wakeup_100", type="speak",
                            text="Show me the Q R code of your wifi, please.")
        self.graph.add_edge("wakeup_02", 
                            "wakeup_100", 
                            label="connect")
        self.graph.add_node("wakeup_101", type="find",
                            what="qr", timeout=5)
        self.graph.add_edge("wakeup_100", 
                            "wakeup_101", 
                            label="show qr")
        self.graph.add_node("wakeup_102", type="update_wifi")
        self.graph.add_edge("wakeup_101", 
                            "wakeup_102", 
                            label="yes")
        self.graph.add_node("wakeup_103", type="speak",
                            text="Do you want me to set up a permanent ip address?")
        self.graph.add_edge("wakeup_102", 
                            "wakeup_103", 
                            label="wifi updated")
        self.graph.add_node("wakeup_104", type="hear",
                            words='["yes", "no"]')
        self.graph.add_edge("wakeup_103", 
                            "wakeup_104", 
                            label="ask")    
        self.graph.add_node("wakeup_105", type="setup_ip")
        self.graph.add_edge("wakeup_104", 
                            "wakeup_105", 
                            label="yes")
        self.graph.add_node("wakeup_106", type="show",
                            text="I will not set up a permanent ip address.")
        self.graph.add_edge("wakeup_105", 
                            "wakeup_106", 
                            label="ip setup done")
        self.graph.add_edge("wakeup_106",
                            "wakeup_01", 
                            label="ip setup done")
        self.graph.add_edge("wakeup_104",
                            "wakeup_107", 
                            label="no") 
        self.graph.add_node("wakeup_107", type="speak",
                            text="I will not set up a permanent ip address.")
        self.graph.add_edge("wakeup_107",
                            "wakeup_01", 
                            label="ip setup done")

        # bye bye---
        self.graph.add_node("wakeup_end", type="speak",
                            text="Bye bye!")
        self.graph.add_edge("wakeup_02", 
                            "wakeup_end", 
                            label="bye")
        self.graph.add_edge("wakeup_end", 
                            "THE END", 
                            label="finished wakeup")

        # run script---
        self.graph.add_node("wakeup_03", type="speak",
                            text="okay, I will run a script. Which one?")
        self.graph.add_edge("wakeup_02", 
                            "wakeup_03", 
                            label="run script")
        # self.graph.add_node("wakeup_04", type="hear", 
        #                     words=script_options)
        self.graph.add_node("wakeup_04", type="find", 
                            what="qr", timeout=5)
        self.graph.add_edge("wakeup_03", 
                            "wakeup_04", 
                            label="run script")

        for sk, sv in list_of_scripts.items():
            self.graph.add_node("wakeup_%s" % sk, type="speak",
                                text="You said %s. Run it?" % sk)
            self.graph.add_edge("wakeup_04", 
                                "wakeup_%s" % sk, 
                                label=sk)
            self.graph.add_node("wakeup_%s_ask" % sk, type="hear",
                                words='["yes", "no"]')
            self.graph.add_edge("wakeup_%s" % sk, 
                                "wakeup_%s_ask" % sk, 
                                label="ask")
            self.graph.add_node("wakeup_%s_yes" % sk, type="script",
                                script=sv, activity=sk,
                                pause={"before": 3})
            self.graph.add_edge("wakeup_%s_ask" % sk, 
                                "wakeup_%s_yes" % sk, 
                                label="yes")
            self.graph.add_edge("wakeup_%s_ask" % sk, 
                                "wakeup_01", 
                                label="no")
            self.graph.add_edge("wakeup_%s_yes" % sk, 
                                "wakeup_04", label="finished")
        self.graph.add_node("The End", type="end")
        
    def find_ip_address(self):
        """
        Find the IP address of the wlan0 interface.
        """
        ip_address = None
        for addr in psutil.net_if_addrs().get("wlan0", []):
            if addr.family == socket.AF_INET:
                ip_address = addr.address
                break
        if ip_address:
            print(f"IP Address: {ip_address}")
            self.data["ip"] = ip_address
        return ip_address
    
    def get_ip(self, current_node, current_data, data_):
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]

        ip_address = self.find_ip_address()
        if ip_address:
            self.graph.nodes[next_node]['caption'] = f"IP Address: {ip_address}"
        return next_node
    
    def update_wifi(self, current_node, current_data, data_):
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]

        wifi_info = list(current_data["found"].keys())[0].split(" ")
        if len(wifi_info) < 2:
            print("No valid WiFi information found in Q R code.")
            return next_node

        self.data["wifi network"] = wifi_info[0]
        self.data["wifi password"] = wifi_info[1]

        cmd = f"sudo nmcli dev wifi connect {self.data['wifi network']} password {self.data['wifi password']}"
        print(f"Executing command: {cmd}")
        result = subprocess.run(
            cmd.split(' '),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print("Command output:", result.stdout)
        print("Command error:", result.stderr)
        if result.returncode != 0:
            print("Failed to connect to WiFi.")
            return next_node

        print(f"Connected to {self.data['wifi network']} with password {self.data['wifi password']}")
        return next_node
        
    def setup_ip(self, current_node, current_data, data_):
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]

        permanent_ip = "0.0.0.0"
        ip_address = self.find_ip_address()
        if ip_address:
            ip_parts = ip_address.split(".")
            ip_parts[-1] = "50"
            permanent_ip = ".".join(ip_parts)
            ip_parts[-1] = "1"
            gateway = ".".join(ip_parts)
            cmds = [
                f"sudo nmcli connection modify {self.data['wifi network']} ipv4.addresses {permanent_ip}/24",
                f"sudo nmcli connection modify {self.data['wifi network']} ipv4.gateway {gateway}",
                f"sudo nmcli connection modify {self.data['wifi network']} ipv4.dns 8.8.8.8",
                f"sudo nmcli connection modify {self.data['wifi network']} ipv4.method manual"
            ]
            for cmd in cmds:
                print(f"Executing command: {cmd}")
                result = subprocess.run(
                    cmd.split(' '),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if result.returncode != 0:
                    print("Failed to set up permanent IP address.")
                    return next_node

        print(f"Permanent IP address set to {permanent_ip}")
        next_node["text"] = f"Permanent IP address set to {permanent_ip}"
        return next_node

if __name__ == "__main__":
    if IS_ROBOT:
        set_speaker_volume(volume_percent=80)

    tasg = WakeUp()
    tasg.init_graph()
    tasg.add_function("get_ip", tasg.get_ip)
    tasg.add_function("update_wifi", tasg.update_wifi)
    tasg.add_function("setup_ip", tasg.setup_ip)

    fuzzy = Character(wakeup=True, activity="wakeup")
    script = Script(graph=tasg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()

    script.run()
        
                


        

