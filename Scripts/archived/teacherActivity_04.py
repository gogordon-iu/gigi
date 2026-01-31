import sys
sys.path.append('../Character')
import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER

teacher_path = "../Assets/teacher/"

# Now that we have the parts and the electronics, let's assemble them together.
# We won't have time to create a whole new robot, like me [hands up and down]
# But we will begin.
# Separate to three groups [look from side to side]. 
# Each group will assemble a different part.
# The first group will connect the orangepi to the base.
# Here is how it should look like. [show video]
# The second group will connect the torso to a motor.
# Here is how it should look like. [show video]
# The last group will connect the screen to the head and ears.
# Here is how it should look like. [show video]
# Please start and if any group needs to see the image again, just say
# Show Group One, Show Group Two, or Show Group Three.
# When you are all done, say Done Gigi.
# Listen to [show group one, show group two, show group three, done, gigi]
# That was amazing. Take it away, Goren!

activity_name = "Teacher activity four"

class TeacherActivity_04(ScriptGraph) : 
    def __init__(self):
        super().__init__()


    def init_graph(self):
        # Add text chunk
        #DEBUG
        self.graph.add_node("start", type=["speak", "move"], 
                            text="Hi again.",
                            motors="wave_hello")
       
        self.graph.add_node("assemble_01", type="audio",
                            audio=teacher_path + 'laugh.wav')
        self.graph.add_edge("start", 
                            "assemble_01", 
                            label="start speak")

        self.graph.add_node("assemble_02", type="speak", 
                            text="Now that we have the parts and the electronics, let's assemble them together.",
                            )

        self.graph.add_node("assemble_03", type=["move", "speak"],
                            motors="arms_up_and_down",
                            text="We won't have time to create a whole new robot, like me.")

        self.graph.add_node("assemble_04", type="speak",
                            text="But we will begin.",
                            pause={"after": 1})

        self.graph.add_node("assemble_05", type=["speak", "move"], 
                            text="Separate to three groups.",
                            motors="look_from_side_to_side")

        self.graph.add_node("assemble_06", type="speak",
                            text="Each group will assemble a different part.",
                            pause={"after": 1})

        self.graph.add_node("assemble_07", type="speak",
                            text="Group number one will connect the orange pi to the base.",
                            pause={"after": 1})
        
        self.graph.add_node("assemble_08", type=["speak", "show"],
                            text="Here is how it should look like.",
                            video="assemble_orangepi.mp4")

        self.graph.add_node("assemble_09", type="speak",
                            text="Group number two will connect the torso to a motor.")
        
        self.graph.add_node("assemble_10", type=["speak", "show"],
                            text="Here is how it should look like.",
                            video="assemble_torso.mp4")

        self.graph.add_node("assemble_11", type="speak",
                            text="Group number three will connect the screen to the head and ears.")
        
        self.graph.add_node("assemble_12", type=["speak", "show"],
                            text="Here is how it should look like.",
                            video="assemble_head.mp4")

        self.graph.add_node("assemble_13", type="speak",
                            text="Please start and if any group needs to see the video again, just say.")

        self.graph.add_node("assemble_14", type="speak",
                            text="Show Group One, Show Group Two, or Show Group Three.")

        self.graph.add_node("assemble_15", type="speak",
                            text="When you are all done, say Done Gigi. You can start.")

        self.graph.add_node("assemble_16", type="hear", 
                            words='["show group one", "show group two", "show group three", "done", "gigi"]')
        
        for i in range(1, 16): 
            self.graph.add_edge("assemble_%02d" % i, 
                                "assemble_%02d" % (i+1), 
                                label="assemble_%02d_%02d" % (i, i+1))

        self.graph.add_node("assemble_16_01", type=["speak", "show"],
                            text="Here is how it should look like.",
                            video="assemble_orangepi.mp4")
        self.graph.add_edge("assemble_16", "assemble_16_01", label="show group one")
        self.graph.add_edge("assemble_16_01", "assemble_16", label="listen_again")

        self.graph.add_node("assemble_16_02", type=["speak", "show"],
                            text="Here is how it should look like.",
                            video="assemble_torso.mp4")
        self.graph.add_edge("assemble_16", "assemble_16_02", label="show group two")
        self.graph.add_edge("assemble_16_02", "assemble_16", label="listen_again")

        self.graph.add_node("assemble_16_03", type=["speak", "show"],
                            text="Here is how it should look like.",
                            video="assemble_head.mp4")
        self.graph.add_edge("assemble_16", "assemble_16_03", label="show group three")
        self.graph.add_edge("assemble_16_03", "assemble_16", label="listen_again")

        self.graph.add_node("assemble_17_01", type="audio",
                            audio=teacher_path + 'laugh.wav')
        self.graph.add_node("assemble_17_02", type="audio",
                            audio=teacher_path + 'laugh.wav')


        self.graph.add_edge("assemble_16", "assemble_17_01", label="done")
        self.graph.add_edge("assemble_16", "assemble_17_02", label="gigi")
        self.graph.add_edge("assemble_17_01", "assemble_17", label="continue")
        self.graph.add_edge("assemble_17_02", "assemble_17", label="continue")

        self.graph.add_node("assemble_17", type="speak",
                            text="That was amazing. Take it away, Goren!")

        self.graph.add_node("The End", type="end")
        self.graph.add_edge("assemble_17", "The End", label="finished")
        
if __name__ == "__main__":
    tasg = TeacherActivity_04()
    tasg.init_graph()

    fuzzy = Character(activity=activity_name, gender='female')
    script = Script(graph=tasg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()

    # script.run()
        
                


        

