import sys
sys.path.append('../Character')
import json
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER
import os

activity_name = "Motor Calibration"

class MotorCalibration(ScriptGraph) : 
    def __init__(self, movement=None):
        super().__init__()

        self.movement = movement
        # basic graph definitions
        if self.movement:
            self.data['motors'] = self.movement.motor_map
        else:
            self.data['motors'] = json.load(open(CHARACTER_FOLDER +  "motorData.json"))
        self.motor_words = "[" + " ".join(["\"%s\"," % m.replace("_", " ")  for m in self.data['motors']]) + "\"[unk]\"]"
        self.number_motors = len(self.data['motors']) + 1
        self.base_angle = 300

    def init_graph(self):
        # Add text chunk
        #DEBUG
        self.graph.add_node("start", type="speak", text="Hi, let's calibrate my motors, together.")
        text = [
            "I am going to move one motor at a time and ask you which joint it is.",
            "It can be either my neck which moves my head.",
            "It can be my torso.",
            "It can be my left or right shoulders.",
            "It can be my left or right elbows.",
            "Let's try"
        ]
        for i, t in enumerate(text):
            self.graph.add_node("text_%d" % i, type="speak", text=t)
            if i > 0:
                self.graph.add_edge("text_%d" % (i-1), "text_%d" % i, label="text_link_%d_%d" % (i-1, i))

        self.graph.add_edge("start", 
                            "text_0", 
                            label="start speak")

        self.graph.add_edge("text_%d" % (len(text)-1), 
                            "channel_move_0",
                            label="start speak")
        
        # self.graph.add_edge("start", 
        #                     "channel_move_0", 
        #                     label="start speak")

        for channel_idx in range(16):
            # move a motor (for a specific channel) and ask if it moved
            self.graph.add_node("channel_move_%d" % channel_idx, type="move", 
                                motors={channel_idx: self.base_angle})

            self.graph.add_node("channel_ask_%d" % channel_idx, type="speak", text="Did something move, say yes or no.")
            self.graph.add_edge("channel_move_%d" % channel_idx, 
                                "channel_ask_%d" % channel_idx, 
                                label="move ask confirmation %d" % channel_idx)

            self.graph.add_node("confirmation_moved_%d" % channel_idx, type="hear", words='["yes", "no", "[unk]"]')
            self.graph.add_edge("channel_ask_%d" % channel_idx, 
                                "confirmation_moved_%d" % channel_idx, 
                                label="ask hear confirmation %d" % channel_idx)
            
            # If it did not move, advance in the channels
            self.graph.add_node("channel_not_moved_%d" % channel_idx, type="speak", text="Trying again.")
            self.graph.add_edge("confirmation_moved_%d" % channel_idx, 
                                "channel_not_moved_%d" % channel_idx,
                                label="no")
            # this will connect to the next channel
            if channel_idx < 15:    # there are more channels to test
                self.graph.add_edge("channel_not_moved_%d" % channel_idx,
                                    "channel_move_%d" % (channel_idx + 1),
                                    label="trying next one")
            else:
                self.graph.add_edge("channel_not_moved_%d" % channel_idx,
                                    "finished",
                                    label="tried last one")

            # if a motor moved, ask for its name
            self.graph.add_node("channel_moved_%d" % channel_idx, type="speak", text="which joint?")
            self.graph.add_edge("confirmation_moved_%d" % channel_idx, 
                                "channel_moved_%d" % channel_idx,
                                label="yes")
            
            self.graph.add_node("confirmation_joint_%d" % channel_idx, type="hear", words=self.motor_words)
            self.graph.add_edge("channel_moved_%d" % channel_idx,
                                "confirmation_joint_%d" % channel_idx,
                                label="what moved")
            
            # calibrate the motor
            for w in self.data['motors'].keys():
                self.graph.add_node("start_calibrate_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Excellent. Now we will calibrate the %s motor." % w)
                self.graph.add_edge("confirmation_joint_%d" % channel_idx,
                                    "start_calibrate_%s_%d" % (w, channel_idx),
                                    label=w.replace("_", " "))
                # start with the "max" calibration
                self.graph.add_node("show_max_%s_%d" % (w, channel_idx), type="show", 
                                    image="%s_max.jpg" % w)
                self.graph.add_edge("start_calibrate_%s_%d" % (w, channel_idx),
                                    "show_max_%s_%d" % (w, channel_idx),
                                    label="show max %s" % w)
                
                self.graph.add_node("explain_max_%s_%d" % (w, channel_idx), type="speak", 
                                    text="I will move my motor until it reaches this position.")
                self.graph.add_edge("show_max_%s_%d" % (w, channel_idx),
                                    "explain_max_%s_%d" % (w, channel_idx),
                                    label="explain max %s" % w)
                
                self.graph.add_node("channel_change_max_%s_%d" % (w, channel_idx), type="change", 
                                    what="angle", by=10)
                self.graph.add_edge("explain_max_%s_%d" % (w, channel_idx),
                                    "channel_change_max_%s_%d" % (w, channel_idx),
                                    label="change max %s" % w)

                self.graph.add_node("channel_move_max_%s_%d" % (w, channel_idx), type="move", 
                                    motors={channel_idx: self.base_angle})
                self.graph.add_edge("channel_change_max_%s_%d" % (w, channel_idx),
                                    "channel_move_max_%s_%d" % (w, channel_idx),
                                    label="move max %s" % w)

                self.graph.add_node("channel_ask_max_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Did the %s reached the shown position? Say yes or no." % w)
                self.graph.add_edge("channel_move_max_%s_%d" % (w, channel_idx), 
                                    "channel_ask_max_%s_%d" % (w, channel_idx),
                                    label="move ask confirmation max %d %s" % (channel_idx, w))

                self.graph.add_node("confirmation_moved_max_%s_%d" % (w, channel_idx), type="hear", 
                                    words='["yes", "no", "[unk]"]')
                self.graph.add_edge("channel_ask_max_%s_%d" % (w, channel_idx), 
                                    "confirmation_moved_max_%s_%d" % (w, channel_idx), 
                                    label="ask hear confirmation_%s_%d" % (w, channel_idx))
                
                self.graph.add_edge("confirmation_moved_max_%s_%d" % (w, channel_idx), 
                                    "channel_change_max_%s_%d" % (w, channel_idx),
                                    label="no")

                self.graph.add_node("update_max_%s_%d" % (w, channel_idx), type="update", 
                                    channel=channel_idx, motor=w, what="max")
                self.graph.add_edge("confirmation_moved_max_%s_%d" % (w, channel_idx), 
                                    "update_max_%s_%d" % (w, channel_idx),
                                    label="yes")


                # continue with the "min" calibration
                self.graph.add_node("show_min_%s_%d" % (w, channel_idx), type="show", 
                                    image="%s_min.jpg" % w)
                self.graph.add_edge("update_max_%s_%d" % (w, channel_idx),
                                    "show_min_%s_%d" % (w, channel_idx),
                                    label="yes")

                self.graph.add_node("explain_min_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Excellent. Let us do the other side. I will move my motor until it reaches this position.")
                self.graph.add_edge("show_min_%s_%d" % (w, channel_idx), 
                                    "explain_min_%s_%d" % (w, channel_idx),
                                     label="explain min %s" % w)
                
                self.graph.add_node("channel_change_min_%s_%d" % (w, channel_idx), type="change", 
                                    what="angle", by=-10)
                self.graph.add_edge("explain_min_%s_%d" % (w, channel_idx),
                                    "channel_change_min_%s_%d" % (w, channel_idx),
                                    label="change min %s" % w)

                self.graph.add_node("channel_move_min_%s_%d" % (w, channel_idx), type="move", 
                    motors={channel_idx: self.base_angle})
                self.graph.add_edge("channel_change_min_%s_%d" % (w, channel_idx),
                                    "channel_move_min_%s_%d" % (w, channel_idx),
                                    label="move min %s" % w)

                self.graph.add_node("channel_ask_min_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Did the %s reached the shown position? Say yes or no." % w)
                self.graph.add_edge("channel_move_min_%s_%d" % (w, channel_idx), 
                                    "channel_ask_min_%s_%d" % (w, channel_idx),
                                    label="move ask confirmation min %d %s" % (channel_idx, w))

                self.graph.add_node("confirmation_moved_min_%s_%d" % (w, channel_idx), type="hear", 
                                    words='["yes", "no", "[unk]"]')
                self.graph.add_edge("channel_ask_min_%s_%d" % (w, channel_idx), 
                                    "confirmation_moved_min_%s_%d" % (w, channel_idx), 
                                    label="ask hear confirmation_%s_%d" % (w, channel_idx))
                
                self.graph.add_edge("confirmation_moved_min_%s_%d" % (w, channel_idx), 
                                    "channel_change_min_%s_%d" % (w, channel_idx),
                                    label="no")

                self.graph.add_node("update_min_%s_%d" % (w, channel_idx), type="update", 
                                    channel=channel_idx, motor=w, what="min")
                self.graph.add_edge("confirmation_moved_min_%s_%d" % (w, channel_idx), 
                                    "update_min_%s_%d" % (w, channel_idx),
                                    label="yes")
                
                self.graph.add_node("stop_show_%s_%d" % (w, channel_idx), type="show", image=None)
                self.graph.add_edge("update_min_%s_%d" % (w, channel_idx), 
                                    "stop_show_%s_%d" % (w, channel_idx),
                                    label="stop show")

                self.graph.add_node("congratulate_%s_%d" % (w, channel_idx), type="speak", 
                                    text="Excellent. We calibrated the %s motor together. Let us continue." % w)
                self.graph.add_edge("stop_show_%s_%d" % (w, channel_idx), 
                                    "congratulate_%s_%d" % (w, channel_idx),
                                     label="congratulate %s" % w)
                
                if channel_idx < 15:    # there are more channels to test
                    self.graph.add_edge("congratulate_%s_%d" % (w, channel_idx),
                                        "channel_move_%d" % (channel_idx + 1),
                                        label="trying next one")
                else:
                    self.graph.add_edge("congratulate_%s_%d" % (w, channel_idx),
                                        "finished",
                                        label="tried last one")        
        self.graph.add_node("finished", type="speak", text="That was an amazing group effort. I am now calibrated.")
        self.graph.add_node("The End", type="end")
        self.graph.add_edge("finished", "The End", label="finished")

    def change(self, current_node, current_data, data_):
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]
        current_channel = int(current_node.split("_")[-1])
        print(next_node)
        print(current_channel)
        change_what = current_data["what"]
        print("DEBUG:", self.data['motors'])
        current_angle = self.graph.nodes[next_node]["motors"][current_channel]
        print('current_angle:', current_angle)
        if change_what == "angle":
            self.graph.nodes[next_node]["motors"][current_channel] = current_angle + current_data["by"]
        return next_node

    def update(self, current_node, current_data, data_):
        self.data['motors'][current_data['motor']]['channel'] = current_data['channel']
        
        motor_name = "channel_move_%s_%s_%d" % (current_data['what'], current_data['motor'], current_data['channel'])
        motor_node = self.graph.nodes[motor_name]
        current_channel = int(current_node.split("_")[-1])
        angle = self.graph.nodes["channel_move_%s_%s_%d" % (current_data['what'], current_data['motor'], current_data['channel'])]['motors'][current_channel]
        self.data['motors'][current_data['motor']][current_data['what']] = angle
        if current_data['what'] == 'min':
            self.data['motors'][current_data['motor']]['calibrated'] = True
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]
        print("Updated: ", self.data['motors'])
        return next_node

    def done(self):
        print(self.data["motors"])
        with open(CHARACTER_FOLDER + "motorData_calibrated.json", "w") as json_file:
            # Save the folder where movement.py was found
            json.dump(self.data['motors'], json_file, indent=4)



if __name__ == "__main__":
    mcsg = MotorCalibration()
    if len(sys.argv) > 1:
        mcsg.base_angle = int(sys.argv[1])
    mcsg.init_graph()
    mcsg.add_function("change", mcsg.change)
    mcsg.add_function("update", mcsg.update)
    mcsg.add_done()

    fuzzy = Character(activity=activity_name, gender='female')
    script = Script(graph=mcsg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()    
    # script.run()