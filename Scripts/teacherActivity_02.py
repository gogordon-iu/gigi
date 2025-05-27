import sys
sys.path.append('../Character')
import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER

teacher_path = "../Assets/teacher/"

# Introduction sequence
# 
# Hi, it's me again, Gigi. [laugh].
# Now that you know a little about me, let's start learning more about how to build more of me.
# [Look down and from side to side]
# In front of you, there are many parts. They were all three D printed.
# There are so many. First, let's sort them.
# I want you to work together and sort them into five piles.
# The first one includes the parts of my base [look down]
# The second includes the parts of my torso [look down]
# Another one for my head [look up]
# One for my right arm [look right]
#  and the last one for the all the parts that make my left arm [look left]
# Work together and discuss [move head from side to side]
# Say "Gigi I'm done", when you are all done.

activity_name = "Teacher activity two"


class TeacherActivity_02(ScriptGraph) : 
    def __init__(self):
        super().__init__()


    def init_graph(self):
        # Add text chunk
        #DEBUG
        self.graph.add_node("start", type=["speak", "move"], 
                            text="Hi, it's me again, Gigi.",
                            motors="wave_hello")
       
        self.graph.add_node("3d_01", type="audio",
                            audio=teacher_path + 'laugh.wav')
        self.graph.add_edge("start", 
                            "3d_01", 
                            label="start speak")

        self.graph.add_node("3d_02", type="speak", 
                            text="Now that you know a little about me, let's start learning more about how to build more of me.")

        self.graph.add_node("3d_03", type=["face", "move", "speak"],
                            face=basic_sequences['look_down'],
                            motors="look_from_side_to_side",
                            text="In front of you, there are many parts. They were all three D printed.",
                            pause={"after": 1})

        self.graph.add_node("3d_04", type=["face", "speak"], 
                            face=basic_sequences['idle'],
                            text="There are so many. ",
                            pause={"after": 1})

        self.graph.add_node("3d_05", type=["speak", "move"], 
                            text="I want you to work together and sort them into five piles.",
                            motors="open_arms")

        self.graph.add_node("3d_06", type=["face", "move", "speak"],
                            face=basic_sequences['look_down'],
                            motors="arms_down",
                            text="The first one includes the parts of my base.",
                            pause={"after": 2})

        self.graph.add_node("3d_07", type=["face", "move", "speak"],
                            face=basic_sequences['look_down'],
                            motors=[
                                {'time': 1,
                                 'motors': {'right_elbow': -0.8,
                                            'left_elbow': 0.8}},
                            ],
                            text="The second includes the parts of my torso.",
                            pause={"after": 2})
        
        self.graph.add_node("3d_08", type=["face", "move", "speak"],
                            face=basic_sequences['look_up'],
                            motors="arms_up",
                            text="Another one for my head.",
                            pause={"after": 2})

        self.graph.add_node("3d_09", type=["face", "move", "speak"],
                            face=basic_sequences['look_right'],
                            motors='wave_right',
                            text="One for my right arm.",
                            pause={"after": 2})

        self.graph.add_node("3d_10", type=["face", "move", "speak"],
                            face=basic_sequences['look_left'],
                            motors='wave_left',
                            text="and the last one for all the parts that make my left arm.",
                            pause={"after": 2})
        
        self.graph.add_node("3d_11", type=["speak", "move"], 
                            text="Work together to sort all the parts that make my body. Discuss among yourselves which part goes where.",
                            motors="open_arms")

        for i in range(1, 11):
            self.graph.add_edge("3d_%02d" % i, 
                                "3d_%02d" % (i+1), 
                                label="3d_%02d_%02d" % (i, i+1))
        
        self.graph.add_node("The End", type="end")
        self.graph.add_edge("3d_11", "The End", label="finished")
        
if __name__ == "__main__":
    tasg = TeacherActivity_02()
    tasg.init_graph()

    fuzzy = Character(activity=activity_name, gender='female')
    script = Script(graph=tasg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    # script.run()
        
                


        

