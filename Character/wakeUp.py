import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER
from scriptAssets import get_scripts
import socket, psutil
from microphone import set_speaker_volume

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
                            words='["run script", "bye", "show wifi"]')
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
                            what="qr")
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
        
    def get_ip(self, current_node, current_data, data_):
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]

        ip_address = None
        for addr in psutil.net_if_addrs().get("wlan0", []):
            if addr.family == socket.AF_INET:
                ip_address = addr.address
                break
        if ip_address:
            print(f"IP Address: {ip_address}")
            self.data["ip"] = ip_address
            self.graph.nodes[next_node]['caption'] = f"IP Address: {ip_address}"
        return next_node
        
if __name__ == "__main__":
    set_speaker_volume(volume_percent=80)

    tasg = WakeUp()
    tasg.init_graph()
    tasg.add_function("get_ip", tasg.get_ip)

    fuzzy = Character(wakeup=True, activity="wakeup")
    script = Script(graph=tasg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()

    script.run()
        
                


        

