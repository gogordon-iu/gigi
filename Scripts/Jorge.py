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
# Name: Jorge
# Character: female
activity_name = 'Jorge'
class Jorge(ScriptGraph) :
    def __init__(self):
        super().__init__()

    def init_graph(self):


        self.graph.add_node('start', type=['character'])
        self.graph.add_edge('start', 'Node_2', label='start_2')
        self.graph.add_node('Node_2', type=['speak', 'move'], text='Hello friends! I`m Gigi the robot!', motors='wave_hello')
        self.graph.add_edge('Node_2', 'Node_3', label='Node_2_3')
        self.graph.add_node('Node_3', type=['speak'], text='We are going to have so much fun today.')
        self.graph.add_edge('Node_3', 'Node_4', label='Node_3_4')
        self.graph.add_node('Node_4', type=['audio'], audio='laugh.wav')
        self.graph.add_edge('Node_4', 'Node_5', label='Node_4_5')
        self.graph.add_node('Node_5', type=['speak'], text='I want to show you what I can do.')
        self.graph.add_edge('Node_5', 'Node_6', label='Node_5_6')
        self.graph.add_node('Node_6', type=['speak', 'move'], text='I can move my arms in a circle', motors='arms_circle')
        self.graph.add_edge('Node_6', 'Node_7', label='Node_6_7')
        self.graph.add_node('Node_7', type=['speak', 'move'], text='I can clap', motors='clap')
        self.graph.add_edge('Node_7', 'Node_8', label='Node_7_8')
        self.graph.add_node('Node_8', type=['speak'], text='Goren can teach me to do almost anything with my body, so just ask him.')
        self.graph.add_edge('Node_8', 'Node_9', label='Node_8_9')
        self.graph.add_node('Node_9', type=['audio'], audio='laugh.wav')
        self.graph.add_edge('Node_9', 'Node_10', label='Node_9_10')
        self.graph.add_node('Node_10', type=['speak'], text='Hope we will have lots of fun dancing together.')
        self.graph.add_edge('Node_10', 'Node_11', label='Node_10_11')
        self.graph.add_node('Node_11', type=['speak', 'move'], text='Bye for now', motors='wave_hello')
        self.graph.add_edge('Node_11', 'Node_12', label='Node_11_12')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Monolingual_Ferris script.')
    parser.add_argument('--offset', type=str, help='Offset from a specific node')
    args = parser.parse_args()
    if not args.offset:
        start_node = 'start'
    else:
        start_node = f"Node_{args.offset}"
    sg = Jorge()
    sg.init_graph()        

    fuzzy = Character(child=False, gender='female', activity='Jorge', languages=['en'])
    script = Script(graph=sg, character=fuzzy)
    script.generateAllSpeech()
    script.check_assets()
    script.run(start_node=start_node)

