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

activity_name = "test activity"

class TestActivity(ScriptGraph) : 
    def __init__(self):
        super().__init__()


    def init_graph(self):
        self.graph.add_node("start", type=["speak", "move"], 
                            text="Hi, I am Gigi. This is a test activity.",
                            motors="wave_hello")
       
        # self.graph.add_node("qr_01", type="find", 
        #                     what="qr", timeout=5)
        # self.graph.add_edge("start", "qr_01", label="start find")

        # self.graph.add_node("qr_02", type="speak", 
        #                     text="Here you are.")
        # self.graph.add_edge("qr_01", "qr_02", label="qr_01_02")

        self.graph.add_node("The End", type="end")
        self.graph.add_edge("start", "The End", label="finished")

        
if __name__ == "__main__":
    tasg = TestActivity()
    tasg.init_graph()

    fuzzy = Character()
    script = Script(graph=tasg, character=fuzzy, activity=activity_name)
    script.generateAllSpeech()
    script.check_assets()
    script.run()
        
                


        

