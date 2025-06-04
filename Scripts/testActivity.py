import sys
sys.path.append('../Character')
import json
import sys
from character import Character
from script import *
from scriptGraph import ScriptGraph
from characterDefinitions import CHARACTER_FOLDER
 
teacher_path = "../Assets/teacher/"

activity_name = "test activity"

class TestActivity(ScriptGraph) : 
    def __init__(self):
        super().__init__()


    def init_graph(self):
        self.graph.add_node("start", type=["speak", "move"], 
                            text="Hi, I am Gigi. This is a test activity.",
                            motors="wave_hello")
       
        self.graph.add_node('Node_14', type=['find'], what='qr', timeout=60, 
                            data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_15', type=['speak'], text='Let me know when you are done by raising the card.')
        self.graph.add_edge('Node_14', 'Node_15', label='no')
        self.graph.add_edge('Node_15', 'Node_14', label='Node_15_14')
        self.graph.add_node('Node_16', type=['speak'], text='Excellent!')
        self.graph.add_edge('Node_14', 'Node_16', label='yes')

        self.graph.add_node('Node_114', type=['find'], what='qr', timeout=60, 
                            data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_115', type=['speak'], text='Let me know when you are done by raising the card.')
        self.graph.add_edge('Node_114', 'Node_115', label='no')
        self.graph.add_edge('Node_115', 'Node_114', label='Node_15_14')
        self.graph.add_node('Node_116', type=['speak'], text='Excellent!')
        self.graph.add_edge('Node_114', 'Node_116', label='yes')

        self.graph.add_node('Node_214', type=['find'], what='qr', timeout=60, 
                            data=['child number 1', 'child number 2', 'child number 3', 'child number 4'])
        self.graph.add_node('Node_215', type=['speak'], text='Let me know when you are done by raising the card.')
        self.graph.add_edge('Node_214', 'Node_215', label='no')
        self.graph.add_edge('Node_215', 'Node_214', label='Node_15_14')
        self.graph.add_node('Node_216', type=['speak'], text='Excellent!')
        self.graph.add_edge('Node_214', 'Node_216', label='yes')

        self.graph.add_edge('start', 'Node_14', label='Node_15_14')
        self.graph.add_edge('Node_16', 'Node_114', label='Node_15_14')
        self.graph.add_edge('Node_116', 'Node_214', label='Node_15_14')
        self.graph.add_edge('Node_216', 'The End', label='finished')

        self.graph.add_node("The End", type="end")
        # self.graph.add_edge("start", "The End", label="finished")

        
if __name__ == "__main__":
    tasg = TestActivity()
    tasg.init_graph()

    fuzzy = Character()
    script = Script(graph=tasg, character=fuzzy, activity=activity_name)
    script.generateAllSpeech()
    script.check_assets()
    script.run()
        
                


        

