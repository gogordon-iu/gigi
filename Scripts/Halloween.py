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
# Name: Halloween
# Character: female
activity_name = 'Halloween'
class Halloween(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):


        self.graph.add_node('start', type=['character'])
        self.graph.add_edge('start', 'Node_2', label='start_2')
        self.graph.add_node('Node_2', type=['speak', 'move'], text='Hello friends! I`m Gigi the robot!', motors='wave_hello')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['speak', 'move'], text='Happy Halloween', motors='look_from_side_to_side')
        self.graph.add_edge('Node_3', 'Node_4', label='Node_3_4')
        self.graph.add_node('Node_4', type=['find'], what='motion', timeout=60)
        self.graph.add_node('Node_5', type=['speak'], text='Hello')
        self.graph.add_edge('Node_4', 'Node_5', label='no')
        self.graph.add_edge('Node_5', 'Node_2', label='Node_5_2')
        self.graph.add_node('Node_6', type=['audio', 'show', 'move'], audio='scream.wav', image='../Assets/Halloween/scary.png', motors='scare')
        self.graph.add_edge('Node_4', 'Node_6', label='yes')
        self.graph.add_edge('Node_6', 'Node_7', label='Node_6_7')
        self.graph.add_node('Node_7', type=['speak', 'face'], text='Trick or treat', face=basic_sequences['smile'])
        self.graph.add_edge('Node_7', 'Node_8', label='Node_7_8')
        self.graph.add_node('Node_8', type=['speak'], text='Bye Bye')
        self.graph.add_edge('Node_8', 'Node_9', label='Node_8_9')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Monolingual_Ferris script.')
    parser.add_argument('--offset', type=str, help='Offset from a specific node')
    args = parser.parse_args()
    if not args.offset:
        start_node = 'start'
    else:
        start_node = f"Node_{args.offset}"
    sg = Halloween()
    sg.init_graph()

    fuzzy = Character(child=False, gender='female', activity='Halloween', languages=['en'])
    script = Script(graph=sg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    script.run(start_node=start_node)

