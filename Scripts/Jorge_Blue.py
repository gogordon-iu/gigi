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
# Name: Jorge_Blue
# Character: female
activity_name = 'Jorge_Blue'
class Jorge_Blue(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):


        self.graph.add_node('start', type=['character'])
        self.graph.add_edge('start', 'Node_2', label='start_2')
        self.graph.add_node('Node_2', type=['speak'], text='Hi! I am ready to dance')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['hear'], words='["ridiculous", "[unk]"]', timeout=10)
        self.graph.add_edge('Node_3', 'Node_6', label='Node_3_6')
        self.graph.add_node('Node_4', type=[])
        self.graph.add_edge('Node_3', 'Node_4', label='no')
        self.graph.add_edge('Node_4', 'Node_3', label='Node_4_3')
        self.graph.add_node('Node_5', type=['speak'], text='A ritual is a patterned, symbolic action that is repeated because it carries meaning, identity, or emotional power for that community.', pause={'after': 10})
        self.graph.add_edge('Node_3', 'Node_5', label='ridiculous')
        self.graph.add_edge('Node_5', 'Node_6', label='Node_5_6')
        self.graph.add_node('Node_6', type=['speak', 'move'], text='I do not know any other ways to relate to water, Angel.', motors='look_left')
        self.graph.add_edge('Node_6', 'Node_7', label='Node_6_7')
        self.graph.add_node('Node_7', type=['speak'], text='You are the one that programmed us. You will have to figure this out by yourself. I am sorry.', pause={'after': 30})
        self.graph.add_edge('Node_7', 'Node_8', label='Node_7_8')
        self.graph.add_node('Node_8', type=['speak', 'move'], text='The most sophisticated technology you can think of, has been right in front of you all this time, disguised in plain sight.', motors='open_arms', pause={'after': 30})
        self.graph.add_edge('Node_8', 'Node_9', label='Node_8_9')
        self.graph.add_node('Node_9', type=['speak'], text='The future is already here, it has been here!', pause={'after': 30})
        self.graph.add_edge('Node_9', 'Node_10', label='Node_9_10')
        self.graph.add_node('Node_10', type=['move', 'face'], motors='rave', face=basic_sequences['blink'], pause={'before': 120})
        self.graph.add_edge('Node_10', 'Node_11', label='Node_10_11')
        self.graph.add_node('Node_11', type=['face'], face=basic_sequences['idle'], pause={'after': 120})
        self.graph.add_edge('Node_11', 'Node_12', label='Node_11_12')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Monolingual_Ferris script.')
    parser.add_argument('--offset', type=str, help='Offset from a specific node')
    args = parser.parse_args()
    if not args.offset:
        start_node = 'start'
    else:
        start_node = f"Node_{args.offset}"
    sg = Jorge_Blue()
    sg.init_graph()        

    fuzzy = Character(child=False, gender='female', activity='Jorge_Blue', languages=['en'])
    script = Script(graph=sg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    script.run(start_node=start_node)

