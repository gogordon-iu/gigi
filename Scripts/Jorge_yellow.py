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
        self.graph.add_node('Node_2', type=['speak'], text='Hi! I am ready to dance')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['find'], what='gesture', timeout=10, data=['Fist', 'OpenHand'])
        self.graph.add_node('Node_4', type=[])
        self.graph.add_edge('Node_3', 'Node_4', label='no')
        self.graph.add_edge('Node_4', 'Node_3', label='Node_4_3')
        self.graph.add_node('Node_5', type=['move', 'show'], motors='jorge_yellow_dance', video='../Assets/Jorge_yellow/jorge_yellow.mp4', pause={'after': 10})
        self.graph.add_edge('Node_3', 'Node_5', label='Fist')
        self.graph.add_edge('Node_5', 'Node_7', label='Node_5_7')
        self.graph.add_node('Node_6', type=['move', 'show'], motors='jorge_yellow_dance', video='../Assets/Jorge_yellow/jorge_yellow.mp4', pause={'after': 10})
        self.graph.add_edge('Node_3', 'Node_6', label='OpenHand')
        self.graph.add_edge('Node_6', 'Node_7', label='Node_6_7')
        self.graph.add_node('Node_7', type=['hear'], words='["yes", "ridiculous", "[unk]"]', timeout=10)
        self.graph.add_edge('Node_7', 'Node_10', label='Node_7_10')
        self.graph.add_node('Node_8', type=[])
        self.graph.add_edge('Node_7', 'Node_8', label='no')
        self.graph.add_edge('Node_8', 'Node_7', label='Node_8_7')
        self.graph.add_node('Node_9', type=['move', 'show'], motors='rave', video='../Assets/Jorge_yellow/jorge_yellow.mp4', pause={'before': 120})
        self.graph.add_edge('Node_7', 'Node_9', label='ridiculous')
        self.graph.add_edge('Node_9', 'Node_10', label='Node_9_10')
        self.graph.add_node('Node_10', type=['show'], video='../Assets/Jorge_yellow/jorge_yellow.mp4', pause={'after': 120})
        self.graph.add_edge('Node_10', 'Node_11', label='Node_10_11')


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

