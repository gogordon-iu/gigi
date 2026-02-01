import sys
sys.path.append('../Character')
import json
import sys
import argparse
from character import Character
from script import *
from scriptGraph import ScriptGraph
import shutil
from characterDefinitions import CHARACTER_FOLDER

# Auto-generated file
# Name: Jorge_yellow
# Character: female
activity_name = 'Jorge_yellow'
class Jorge_yellow(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):


        self.graph.add_node('start', type=['character'])
        self.graph.add_edge('start', 'Node_2', label='start_2')
        self.graph.add_node('Node_2', type=['speak', 'show'], text='Hi! I am ready to dance', video='../Assets/Jorge_yellow/jorge_yellow.mov.mp4')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['find'], what='gesture', timeout=10, data=['Fist', 'OpenHand'])
        self.graph.add_node('Node_4', type=[])
        self.graph.add_edge('Node_3', 'Node_4', label='no')
        self.graph.add_edge('Node_4', 'Node_3', label='Node_4_3')
        self.graph.add_node('Node_5', type=['move'], motors='jorge_yellow_dance', pause={'after': 10})
        self.graph.add_edge('Node_3', 'Node_5', label='Fist')
        self.graph.add_edge('Node_5', 'Node_6', label='Node_5_6')
        self.graph.add_node('Node_6', type=['move'], motors='jorge_yellow_dance', pause={'after': 10})
        self.graph.add_edge('Node_3', 'Node_6', label='OpenHand')
        self.graph.add_edge('Node_6', 'Node_7', label='Node_6_7')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Monolingual_Ferris script.')
    parser.add_argument('--offset', type=str, help='Offset from a specific node')
    args = parser.parse_args()
    if not args.offset:
        start_node = 'start'
    else:
        start_node = f"Node_{args.offset}"
    sg = Jorge_yellow()
    sg.init_graph()        

    fuzzy = Character(child=False, gender='female', activity='Jorge_yellow', languages=['en'])
    script = Script(graph=sg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    script.run(start_node=start_node)

