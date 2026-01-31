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
# Hi. I am Gigi [wave hello]. 
# I am a social robot and I want to help children learn.
# I can do lots of things, like look at you.
# I can also perform gestures, like these [arms wide open].
# If I need to show things, I can hide my face and present what is needed instead, like this.
# [show image]
# [laugh] That was funny, me showing me [smile].
# I'm also a very good listener. Do you want to see, answer with yes or no?
# [yes, no] -- > you said [yes,no]. [laughs] I just demonstrated that I can hear you.
# Enough about what I can do, let's talk about how I came to be.
# One of the special things about me, is that you, or your students, can build me, or social robots like me.
# Hopefully, today, we will work together towards learning how to do that.
# Goren, do you want to say a few words?

activity_name = "Teacher activity one"

class TeacherActivity_01(ScriptGraph) : 
    def __init__(self):
        super().__init__()


    def init_graph(self):
        # Add text chunk
        #DEBUG
        self.graph.add_node("start", type=["speak", "move"], 
                            text="Hi, I am Gigi.",
                            motors="wave_hello")
       
        self.graph.add_node("intro_02", type="speak",
                            text="I am a social robot and I want to help children learn.",
                            pause={"after": 2}
                            )
        self.graph.add_edge("start", 
                            "intro_02", 
                            label="start speak")

        # Bug fix: intro_03 was a duplicate
        self.graph.add_node("intro_04", type="speak", 
                            text="I can do lots of things. One of them is to look at you.")
        self.graph.add_edge("intro_02", 
                            "intro_04", 
                            label="intro_03_04")

        self.graph.add_node("intro_05", type="find", 
                            what="face", timeout=5)
        self.graph.add_edge("intro_04", 
                            "intro_05", 
                            label="intro_04_05")

        self.graph.add_node("intro_05_yes", type="speak", 
                            text="Here you are. I used my camera to find your face.",
                            pause={"after": 1})
        self.graph.add_edge("intro_05", 
                            "intro_05_yes", 
                            label="yes")
        self.graph.add_node("intro_05_no", type="speak", 
                            text="Where are you?")
        self.graph.add_edge("intro_05", 
                            "intro_05_no", 
                            label="no")
        self.graph.add_edge("intro_05_no", 
                            "intro_05", 
                            label="intro_05_05")

        self.graph.add_node("intro_06", type=["speak", "move"], 
                            text="I can also perform gestures, like waving hello.",
                            motors="wave_hello")
        self.graph.add_edge("intro_05_yes", 
                            "intro_06", 
                            label="intro_05_06")

        self.graph.add_node("intro_07", type="speak",
                            text="If I need to show things.",
                            pause={"before": 1})
        self.graph.add_edge("intro_06", 
                            "intro_07", 
                            label="intro_06_07")
        self.graph.add_node("intro_07.5", type=["speak", "show"],
                            text="I can hide my face and present what is needed instead, like this.",
                            image=teacher_path + "gigi.jpg")
        self.graph.add_edge("intro_07", 
                            "intro_07.5", 
                            label="intro_06_07")

        self.graph.add_node("intro_08", type="audio",
                            audio=teacher_path + 'laugh.wav')
        self.graph.add_edge("intro_07.5", 
                            "intro_08", 
                            label="intro_07_08")

        self.graph.add_node("intro_09", type=["speak", "show"],
                            text="That was funny, me showing me.",
                            image=None,
                            pause={"after":1})
        self.graph.add_edge("intro_08", 
                            "intro_09", 
                            label="intro_08_09")
        
        self.graph.add_node("intro_10", type="speak",
                            text="I'm also a very good listener. If you want to see that, say yes.")
        self.graph.add_edge("intro_09", 
                            "intro_10", 
                            label="intro_09_10")
        
        self.graph.add_node("intro_11", type="hear", words='["yes", "no", "[unk]"]')
        self.graph.add_edge("intro_10", 
                            "intro_11", 
                            label="intro_10_11")

        self.graph.add_node("intro_11_01", type="speak",
                            text="You said yes.")
        self.graph.add_edge("intro_11", 
                            "intro_11_01", 
                            label="yes")

        self.graph.add_node("intro_11_02", type="speak",
                            text="You said no.")
        self.graph.add_edge("intro_11", 
                            "intro_11_02", 
                            label="no")

        self.graph.add_node("intro_12", type="audio",
                            audio=teacher_path + 'laugh.wav')
        self.graph.add_edge("intro_11_01", 
                            "intro_12", 
                            label="intro_11_12")
        self.graph.add_edge("intro_11_02", 
                            "intro_12", 
                            label="intro_11_12")

        self.graph.add_node("intro_13", type="speak",
                            text="I just demonstrated that I can hear you.",
                            pause={"after": 1})
        self.graph.add_edge("intro_12", 
                            "intro_13", 
                            label="intro_12_13")

        self.graph.add_node("intro_14", type="speak",
                            text="Enough about what I can do, let's talk about how I came to be.")
        self.graph.add_edge("intro_13", 
                            "intro_14", 
                            label="intro_13_14")

        self.graph.add_node("intro_14_2", type="speak",
                            text="One of the special things about me, is that you, or your students, can build me, or social robots like me. ",
                            pause={"after": 1})
        self.graph.add_edge("intro_14", 
                            "intro_14_2", 
                            label="intro_13_14")
        self.graph.add_node("intro_14_3", type="speak",
                            text="Hopefully, today, we will work together towards learning how to do that.")
        self.graph.add_edge("intro_14_2", 
                            "intro_14_3", 
                            label="intro_13_14")

        self.graph.add_node("intro_15", type=["speak", "face"],
                            text="Goren, do you want to say a few words?",
                            face="look_left",
                            pause={"before": 1})
        self.graph.add_edge("intro_14_3", 
                            "intro_15", 
                            label="intro_14_15")

        self.graph.add_node("The End", type="end")
        self.graph.add_edge("intro_15", "The End", label="finished")

        
if __name__ == "__main__":
    tasg = TeacherActivity_01()
    tasg.init_graph()

    fuzzy = Character(activity=activity_name, gender='female')
    script = Script(graph=tasg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    # script.run()
        
                


        

