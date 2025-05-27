import sys
sys.path.append('../Character')
import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER

teacher_path = "../Assets/Teacher_activity_three/"

# I'm back.
# You did great with the three D printed parts.
# Now, we will work on the electronic parts.
# Each one has an electronic part that makes up ... well ... me.
# [laugh]
# Let's go one by one [look from side to side]
# Each one, pick up the part you have in front of you and tell the others, what do you think it is.
# When you are done, simply say "Done, gigi."
#[[do look at and listen to "done", "gigi"]]
# "done/gigi" --> That is great, let's move to the next one.
# Repeat this [Orangepi, power, battery, controller, motors, camera, button]
# Excellent! Now that you have all the parts, there are wires in the middle of the table.
# Try to connect all the things together.
# Be careful! Do not switch the power button on. It should be on O (show picture) and off.
# When you're done, say "Done Gigi".
# --> That is interesting. Goren, take it from here.

parts = ["Orangepi", "power", "battery", "controller", "motors", "camera", "button"]

activity_name = "Teacher activity three"

class TeacherActivity_03(ScriptGraph) : 
    def __init__(self):
        super().__init__()


    def init_graph(self):
        # Add text chunk
        #DEBUG
        self.graph.add_node("start", type=["speak", "move"], 
                            text="I'm back.",
                            motors="wave_hello")
       
        self.graph.add_node("electric_01", type="audio",
                            audio='laugh.wav')
        self.graph.add_edge("start", 
                            "electric_01", 
                            label="start speak")

        self.graph.add_node("electric_02", type=["speak", "move"], 
                            text="You did great with the three D printed parts.",
                            motors="clap")

        self.graph.add_node("electric_03", type=["face", "move", "speak"],
                            face=basic_sequences['look_down'],
                            motors="look_from_side_to_side",
                            text="Now, we will work on the electronic parts.")

        self.graph.add_node("electric_04", type=["face", "speak"], 
                            face=basic_sequences['idle'],
                            text="Each one has an electronic part that makes up. Me.")

        self.graph.add_node("electric_05", type="audio", 
                            audio='laugh.wav')

        self.graph.add_node("electric_06", type=["move", "speak"],
                            motors="look_from_side_to_side",
                            text="Let's go one by one.")

        self.graph.add_node("electric_07", type="speak",
                            text="Each one, pick up the part you have in front of you and tell the others, what do you think it is.")
        
        self.graph.add_node("electric_08", type="speak",
                            text="When you are done, simply say: Done, gigi.")

        self.graph.add_node("electric_09", type="find", 
                            what="face", timeout=5)
        for i in range(1, 9):
            self.graph.add_edge("electric_%02d" % i, 
                                "electric_%02d" % (i+1), 
                                label="electric_%02d_%02d" % (i, i+1))
        self.graph.add_edge("electric_09", "electric_10_01_01", label="yes")

        for i in range(0, len(parts)):
            if i == 0:
                text = "You can start. When you are finished, say: done, gigi."
            elif i == len(parts)-1:
                text = "Now for the last one. . When you are finished, say: done, gigi."
            else:
                text="That is great, let's move to the next one. When you are finished, say: done, gigi."

            self.graph.add_node("electric_10_%02d_01" % (i+1), type="speak",
                                text=text)
            
            self.graph.add_node("electric_10_%02d_02" % (i+1), type="hear", 
                                words='["done", "gigi", "[unk]"]')

            self.graph.add_edge("electric_10_%02d_01" % (i+1), 
                                "electric_10_%02d_02" % (i+1), 
                                label="electric_10_%02d_1-2" % (i+1))
            if i < (len(parts) - 1):
                self.graph.add_node("electric_10_%02d_02_01" % (i+1), type="audio", 
                                    audio='laugh.wav')
                self.graph.add_node("electric_10_%02d_02_02" % (i+1), type="audio", 
                                    audio='laugh.wav')

                self.graph.add_edge("electric_10_%02d_02" % (i+1), 
                                    "electric_10_%02d_02_01" % (i+1), 
                                    label="done")
                self.graph.add_edge("electric_10_%02d_02" % (i+1), 
                                    "electric_10_%02d_02_02" % (i+1), 
                                    label="gigi")
                self.graph.add_edge("electric_10_%02d_02_01" % (i+1), 
                                    "electric_10_%02d_01" % (i+2), 
                                    label="continue")
                self.graph.add_edge("electric_10_%02d_02_02" % (i+1), 
                                    "electric_10_%02d_01" % (i+2), 
                                    label="continue")
                

        self.graph.add_node("electric_11_01", type="audio", 
                            audio='laugh.wav')
        self.graph.add_node("electric_11_02", type="audio", 
                            audio='laugh.wav')

        self.graph.add_edge("electric_10_%02d_02" % len(parts), 
                            "electric_11_01", label="done")
        self.graph.add_edge("electric_10_%02d_02" % len(parts), 
                            "electric_11_02", label="gigi")

        self.graph.add_edge("electric_11_01", 
                            "electric_11", label="continue")
        self.graph.add_edge("electric_11_02", 
                            "electric_11", label="continue")


        self.graph.add_node("electric_11", type="speak",
                            text="Excellent! You now have all the parts.")

        # self.graph.add_node("electric_12", type=["speak", "face"],
        #                     text="Try to connect all the things together.",
        #                     face=basic_sequences['look_down'])
        
        self.graph.add_node("electric_12", type=["speak", "show"],
                            text="Be careful! Do not switch the power button on. It should be on O and off.",
                            image="button_off.jpg")
        self.graph.add_edge("electric_11", "electric_12", label="goren")

        # self.graph.add_node("electric_13", type="speak",
        #                     text="When you're done, say: Done Gigi")

        # self.graph.add_node("electric_14", type="hear", 
        #                     words='["done", "gigi", "[unk]"]')

        # for i in range(11, 14):
        #     self.graph.add_edge("electric_%02d" % i, 
        #                         "electric_%02d" % (i+1), 
        #                         label="electric_%02d_%02d" % (i, i+1))
        # self.graph.add_edge("electric_14", "electric_15", label="done")
        # self.graph.add_edge("electric_14", "electric_15", label="gigi")

        self.graph.add_edge("electric_12", "electric_15", label="goren")
        self.graph.add_node("electric_15", type="speak",
                            text="Goren, take it from here.")

        self.graph.add_node("The End", type="end")
        self.graph.add_edge("electric_15", "The End", label="finished")
        
if __name__ == "__main__":
    tasg = TeacherActivity_03()
    tasg.init_graph()

    fuzzy = Character(activity=activity_name, gender='female')
    script = Script(graph=tasg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()

    # script.run()
        
                


        

