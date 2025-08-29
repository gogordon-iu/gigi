import sys
sys.path.append('../Character')
import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER
 
teacher_path = "../Assets/teacher/"

activity_name = "test_activity"

class TestActivity(ScriptGraph) : 
    def __init__(self):
        super().__init__()


    def init_graph(self):
        self.graph.add_node("start", type=["speak", "move"], 
                            text="Hi, I am Gigi. This is a test activity.",
                            motors="wave_hello")
        self.graph.add_node('Node_300', type=['speak'], text='Would you like to play with me? #¿Quieren jugar conmigo? #')
        self.graph.add_edge('start', 'Node_300', label='Node_15_14')
        self.graph.add_edge('Node_300', 'The End', label='finished')

        self.graph.add_node("The End", type="end")
        # self.graph.add_edge("start", "The End", label="finished")

        
if __name__ == "__main__":
    tasg = TestActivity()
    tasg.init_graph()

    fuzzy = Character(child=False, gender='female', activity='test_activity', languages=['en', 'es'])

    # fuzzy = Character()
    script = Script(graph=tasg, character=fuzzy, activity=activity_name)
    script.generateAllSpeech()
    script.check_assets()
    script.run()
        
                


        

