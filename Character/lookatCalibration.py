import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER


# hi, i want to be able to look at you
# First let me find your face
# -- find face, let know that I found it
# great, i can see you
# now, I will move my head. you move yours until you look into my eyes. When you do, say "done"

class LookatCalibration(ScriptGraph) : 
    def __init__(self, vision=None):
        super().__init__()

        self.vision = vision
        self.data['calibration'] = {}


    def init_graph(self):
        # Add text chunk
        #DEBUG
        self.graph.add_node("start", type="speak", text="Hi, i want to be able to look at you.")
       
        self.graph.add_node("find_face_speak", type="speak", text="First, let me find your face.")
        self.graph.add_edge("start", 
                            "find_face_speak", 
                            label="start speak")
        
        self.graph.add_node("find_face_first", type="find", what="face")
        self.graph.add_edge("find_face_speak", 
                            "find_face_first", 
                            label="find face")
        
        # did not find, enter a loop until found
        self.graph.add_node("not_found_face_first", type="speak", text="Oh, I can't see you. Let's try again.")
        self.graph.add_edge("find_face_first", 
                            "not_found_face_first", 
                            label="no")
        self.graph.add_edge("not_found_face_first", 
                            "find_face_first", 
                            label="try again to find face")
        
        # found a face
        self.graph.add_node("found_face_first", type="speak", text="Great, I can see you.")
        self.graph.add_edge("find_face_first", 
                            "found_face_first", 
                            label="yes")

        self.graph.add_node("calibrate_speak", type="speak", label="yes", 
                            text="Now, I will move my head. You move yours until you look into my eyes. When you do, say DONE.")
        self.graph.add_edge("found_face_first", 
                            "calibrate_speak", 
                            label="start calibration")

        self.graph.add_edge("calibrate_speak", 
                            "calibrate_move_0", 
                            label="start_move_0")

        calibration_points = [0.3, 0.6, 0.9, -0.3, -0.6, -0.9]

        for i, calibration in enumerate(calibration_points):
            self.graph.add_node("calibrate_move_%d" % i, type="move", motors={"neck": calibration})

            self.graph.add_node("calibrate_hear_%d" % i, type="hear", words='["done", "[unk]"]')
            self.graph.add_edge("calibrate_move_%d" % i, "calibrate_hear_%d" % i, label="move_hear_%d" %i)

            self.graph.add_node("find_face_%d" % i, type="find", what="face")
            self.graph.add_edge("calibrate_hear_%d" % i, "find_face_%d" % i, label="done")

            self.graph.add_node("not_found_face_%d" % i, type="speak", text="Oh, I can't see you. Let's try again.")
            self.graph.add_edge("find_face_%d" % i, 
                                "not_found_face_%d" % i, 
                                label="no")
            self.graph.add_edge("not_found_face_%d" % i, 
                                "find_face_%d" % i,
                                label="no")

            self.graph.add_node("calibrate_update_%d" % i, type="update", data=calibration)
            self.graph.add_edge("find_face_%d" % i, 
                                "calibrate_update_%d" % i, 
                                label="yes")

            if i < (len(calibration_points)-1):
                self.graph.add_node("calibrate_speak_%d" % i, type="speak", text="excellent, let's continue.")
                self.graph.add_edge("calibrate_update_%d" % i, "calibrate_speak_%d" % i, label="speak congratulations")
                self.graph.add_edge("calibrate_speak_%d" % i, "calibrate_move_%d" % (i+1), label="speak_move_%d" %i)

        self.graph.add_node("calibrate_finished_speak", type=["speak", "move"],
                    text="That was amazing, I can now look at your face during our activitiers together.",
                    motors={"neck": 0.0})
        self.graph.add_edge("calibrate_update_%d" % (len(calibration_points) - 1), "calibrate_finished_speak", label="done")

        self.graph.add_node("The End", type="end")
        self.graph.add_edge("calibrate_finished_speak", "The End", label="finished")

    def update(self, current_node, current_data, data_):
        if self.vision:
            face_coor = next(iter(self.vision.found['face'].values()))['offset']
            self.data['calibration'][current_data['data']] = face_coor

            print(self.data['calibration'])
        edges = self.graph.out_edges(current_node, data=True)
        next_node = list(edges)[0][1]
        return next_node

    def done(self):
        with open("lookat_calibrated.json", "w") as json_file:
            json.dump(self.data['calibration'], json_file, indent=4)

        
if __name__ == "__main__":
    fuzzy = Character()

    lcsg = LookatCalibration(vision=fuzzy.vision)
    lcsg.init_graph()
    lcsg.add_function("update", lcsg.update)
    lcsg.add_done(lcsg.done)

    script = Script(graph=lcsg, character=fuzzy)

    script.generateAllSpeech()

    fuzzy.movement.home_position()

    script.run()
        
                


        

