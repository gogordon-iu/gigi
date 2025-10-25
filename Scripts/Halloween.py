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
        self.graph.add_node('Node_3', type=['speak', 'move'], text='I will hide here quietly and scare people', motors='arms_down')
        self.graph.add_edge('Node_3', 'Node_4', label='Node_3_4')
        self.graph.add_node('Node_4', type=['show'], image='../Assets/Halloween/hide.png')
        self.graph.add_edge('Node_4', 'Node_5', label='Node_4_5')
        self.graph.add_node('Node_5', type=['find'], what='motion', timeout=60)
        self.graph.add_node('Node_6', type=['speak'], text='hiding')
        self.graph.add_edge('Node_5', 'Node_6', label='no')
        self.graph.add_edge('Node_6', 'Node_5', label='Node_6_5')
        self.graph.add_node('Node_7', type=['audio', 'show', 'move'], audio='scream.wav', image='../Assets/Halloween/scary.png', motors='arms_up')
        self.graph.add_edge('Node_5', 'Node_7', label='yes')
        self.graph.add_edge('Node_7', 'Node_8', label='Node_7_8')
        self.graph.add_node('Node_8', type=['speak', 'face'], text='Trick or treat', face=basic_sequences['smile'])
        self.graph.add_edge('Node_8', 'Node_9', label='Node_8_9')
        self.graph.add_node('Node_9', type=['speak'], text='Do you want me to do that again?')
        self.graph.add_edge('Node_9', 'Node_10', label='Node_9_10')
        self.graph.add_node('Node_10', type=['hear'], words='["yes", "no", "[unk]"]')
        self.graph.add_node('Node_11', type=[])
        self.graph.add_edge('Node_10', 'Node_11', label='yes')
        self.graph.add_edge('Node_11', 'Node_3', label='Node_11_3')
        self.graph.add_node('Node_12', type=['speak'], text='That was fun. Happy Halloween')
        self.graph.add_edge('Node_10', 'Node_12', label='no')
        self.graph.add_edge('Node_12', 'Node_13', label='Node_12_13')


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

