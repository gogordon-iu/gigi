import json
from script import *
from scriptGraph import ScriptGraph


class MotorCalibration(ScriptGraph) : 
    def __init__(self, movement=None):
        super().__init__()

        self.movement = movement
        # basic graph definitions
        if self.movement:
            self.motors = self.movement.motor_map
        else:
            self.motors = json.load(open("motorData.json"))
        for m in self.motors:
            self.motors[m]['calibrated']=False
        self.motor_words = "[" + " ".join(["\"%s\"," % m  for m in self.motors]) + "\"[unk]\"]"
        self.number_motors = len(self.motors) + 1
        self.base_angle = 50

    def init_graph(self):
        # Add text chunk
        self.graph.add_node("start", type="speak", text="Hi, let's calibrate my self.motors, together OK?")
        text = [
            "I am going got move one motor at a time and ask you which joint it is.",
            "It can be either my neck which moves my head",
            "It can be my torso",
            "It can be my left or right shoulders",
            "It can be my left or right elbows",
            "Let's try"
        ]
        for i, t in enumerate(text):
            self.graph.add_node("text_%d" % i, type="speak", text=t)
            if i > 0:
                self.graph.add_edge("text_%d" % (i-1), "text_%d" % i, label="text_link_%d_%d" % (i-1, i))

        self.graph.add_node("motor_move", type="move", motors={"neck": self.base_angle})
        self.graph.add_node("motor_ask", type="speak", text="Did something move, say yes or no")
        self.graph.add_node("confirmation_moved", type="hear", words='["yes", "no", "[unk]"]')
        self.graph.add_node("motor_not_moved", type="change", what="angle", by=10)
        self.graph.add_node("motor_moved", type="speak", text="which joint?")
        self.graph.add_node("confirmation_joint", type="hear", words=self.motor_words)
        self.graph.add_node("check_next_motor", type="check")
        self.graph.add_node("change_motor", type="speak", text="great, lets continue")
        self.graph.add_node("finished", type="speak", text="great, we finished")

        self.graph.add_edge("start", "text_0", label="first text")
        self.graph.add_edge("text_%d" % (len(text) - 1), "motor_move", label="last text")

        # move and confirm
        self.graph.add_edge("motor_move", "motor_ask", label="ask move confirmation")
        self.graph.add_edge("motor_ask", "confirmation_moved", label="hear confirmation")

        self.graph.add_edge("confirmation_moved", "motor_not_moved", label="no")
        self.graph.add_edge("motor_not_moved", "motor_move", label="increase angle")

        self.graph.add_edge("confirmation_moved", "motor_moved", label="yes")
        self.graph.add_edge("motor_moved", "confirmation_joint", label="ask for joint")

        # get joint
        for m in self.motors:
            motor_node = "%s_moved" % m
            self.graph.add_node(motor_node, type="change", what="motor", by=1)
            self.graph.add_edge("confirmation_joint", motor_node, label=m)
            self.graph.add_edge(motor_node, "check_next_motor", label="congratulate")

        #move to next motor
        self.graph.add_edge("check_next_motor", "change_motor", label="next motor")
        self.graph.add_edge("change_motor", "motor_move", label="next motor")
        self.graph.add_edge("check_next_motor", "finished", label="finished")


    def change(self, current_node, current_data, data_):
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]
        change_what = current_data["what"]
        print("DEBUG:", self.motors)
        current_motor = list(self.graph.nodes["motor_move"]["motors"].keys())[0]
        current_angle = self.graph.nodes["motor_move"]["motors"][current_motor]
        if change_what == "angle":
            self.graph.nodes["motor_move"]["motors"][current_motor] = current_angle + current_data["by"]
        elif change_what == "motor":
            # if finished with this motor, save it to the outputs in the format: motor ] = [min_angle, max_angle]
            data_['output'][current_motor] = [current_angle, current_angle]
            uncalibrated = [m for m in self.motors if not(self.motors[m]['calibrated'])]

            if len(uncalibrated) > 0:
                current_motor = uncalibrated[0]
                self.graph.nodes["motor_move"]["motors"] = {current_motor : self.base_angle}
            else:
                self.graph.nodes["motor_move"]["motors"] = None
        return next_node

    def check(self, current_node, current_data, data_):
        motors = self.graph.nodes["motor_move"]["motors"]
        if motors:
            next_node = next((edge for edge in self.graph.out_edges(current_node, data=True) if edge[2].get("label") == "next motor"), None)[1]
        else:
            next_node = next((edge for edge in self.graph.out_edges(current_node, data=True) if edge[2].get("label") == "finished"), None)[1]
        return next_node

    def hear(self, current_node, current_data, data_):
        print("Hear, listening for one of the following: ", current_data["words"])
        edges = self.graph.out_edges(current_node, data=True)
        motor = list(self.graph.nodes["motor_move"]["motors"].keys())[0]

        if "yes" in current_data["words"]:      # yes/no
            print("DEBUG: ", self.graph.nodes["motor_move"]["motors"].values())
            angle = self.graph.nodes["motor_move"]["motors"][motor]
            if angle < 80:
                output = "no"
            else:
                output = "yes"
        elif "neck" in current_data["words"]:   #joints
            output = motor

        print("hear output: ", output)
        for u, v, current_data in edges:
            if current_data['label'] == output:
                next_node = v
                break
        return next_node

    def done(self):
        print(self.data["output"])
        # with open("motorData.json", "w") as json_file:
        #     json.dump(self.data["output"], json_file, indent=4)


    def init_graph2(self):
        # Add text chunk
        self.graph.add_node("next_part", type="speak", text="Great, now we mapped the different channels to specific motors")
        self.graph.add_edge("finished", "next_part", label="start next part")       
        text = [
            "Now we need to find the boundaries of each motor.",
            "I'll go one motor at a time, start with the smallest angle and increase it, until you tell me it arrived at the maximum angle.",
            "For each motor, I will show you how it should look like",
            "Let's start"
        ]
        for i, t in enumerate(text):
            self.graph.add_node("text2_%d" % i, type="speak", text=t)
            if i > 0:
                self.graph.add_edge("text2_%d" % (i-1), "text2_%d" % i, label="text2_link_%d_%d" % (i-1, i))
        
        self.graph.add_edge("next_part", "text2_0", label="last text")
        self.graph.add_node("The End", type="end")
        self.graph.add_edge("text2_3", "The End", label="finished2")
        



if __name__ == "__main__":
    mcsg = MotorCalibration()
    mcsg.init_graph()
    mcsg.init_graph2()    
    mcsg.add_function("change", mcsg.change)
    mcsg.add_function("check", mcsg.check)
    mcsg.add_function("hear", mcsg.hear)
    mcsg.add_done()

    # fuzzy = Character()
    script = Script(graph=mcsg)
    script.run()